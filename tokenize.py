#!/usr/bin/env python3
"""
Simple SQL Tokenizer and Table Extractor for PostgreSQL.
Hand-rolled lexer (no regex).
Updated with --search TABLE_NAME, summary, JSON/CSV output, directory support, and robustness fixes.
"""

import os
import sys
import argparse
import json
import csv
from typing import List, Tuple
from pathlib import Path

# Token types
KEYWORD = 'KEYWORD'
KOI = 'KOI'
IDENTIFIER = 'IDENTIFIER'
OPERATOR = 'OPERATOR'
SPECIAL = 'SPECIAL'
CONSTANT = 'CONSTANT'
COMMENT = 'COMMENT'
UNKNOWN = 'UNKNOWN'
EOF = 'EOF'

TABLE_KOI = {'from', 'join', 'into', 'with'}
SQL_KEYWORDS = {
    'select', 'insert', 'delete', 'update', 'create', 'drop', 'alter',
    'table', 'view', 'on', 'where', 'group', 'by', 'having', 'order',
    'left', 'right', 'inner', 'outer', 'full', 'cross', 'natural',
    'as', 'values', 'set', 'and', 'or', 'not', 'is', 'null'
}
SPEC_CHARS = {'(', ')', ',', ';', '.', '[', ']', '{', '}', '$', ':'}
OPERATORS = {'+', '-', '*', '/', '=', '<', '>', '!', '~', '@', '%', '^', '&', '|', '`', '?', '::'}
WHITESPACE = {' ', '\t', '\n', '\r'}


class Token:
    def __init__(self, token_type: str, value: str):
        self.type = token_type
        self.value = value

    def __str__(self):
        return f"Token({self.type}, {repr(self.value)})"


class Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens: List[Token] = []

    def _current(self):
        return self.text[self.pos] if self.pos < len(self.text) else None

    def _advance(self):
        self.pos += 1

    def _skip_whitespace(self):
        while self._current() in WHITESPACE:
            self._advance()

    def _skip_comment(self):
        if self._current() == '-' and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '-':
            start = self.pos
            while self._current() is not None and self._current() != '\n':
                self._advance()
            return Token(COMMENT, self.text[start:self.pos])
        return None

    def _get_string(self):
        """Consume a single-quoted string constant."""
        quote = self._current()
        start = self.pos
        self._advance()
        while self._current() is not None:
            if self._current() == quote:
                self._advance()
                break
            if self._current() == '\\':
                self._advance()
                if self._current() is not None:
                    self._advance()
                continue
            self._advance()
        return Token(CONSTANT, self.text[start:self.pos])

    def _get_quoted_identifier(self):
        """
        Consume a double-quoted identifier: "schema"."table" style.
        Reads one quoted segment at a time; the dot between segments
        is emitted as a SPECIAL token by the main tokenize() loop.
        """
        start = self.pos
        self._advance()  # consume opening "
        while self._current() is not None:
            if self._current() == '"':
                # Handle escaped double-quote ("") inside identifier
                if self.pos + 1 < len(self.text) and self.text[self.pos + 1] == '"':
                    self._advance()  # skip first "
                    self._advance()  # skip second "
                    continue
                self._advance()  # consume closing "
                break
            self._advance()
        raw = self.text[start:self.pos]
        # Strip the surrounding quotes for classification
        value = raw[1:-1].lower() if len(raw) >= 2 else raw.lower()
        if value in TABLE_KOI:
            return Token(KOI, value)
        elif value in SQL_KEYWORDS:
            return Token(KEYWORD, value)
        return Token(IDENTIFIER, value)

    def _get_number(self):
        start = self.pos
        while self._current() is not None and (self._current().isdigit() or self._current() in {'.', 'e', 'E', '+', '-'}):
            self._advance()
        return Token(CONSTANT, self.text[start:self.pos])

    def _get_identifier(self):
        """Consume an unquoted identifier or keyword."""
        start = self.pos
        while self._current() is not None and (self._current().isalnum() or self._current() in {'_', '$'}):
            self._advance()
        value = self.text[start:self.pos].lower()
        if value in TABLE_KOI:
            return Token(KOI, value)
        elif value in SQL_KEYWORDS:
            return Token(KEYWORD, value)
        return Token(IDENTIFIER, value)

    def _get_operator(self):
        start = self.pos
        while self._current() is not None and self._current() in ''.join(OPERATORS):
            self._advance()
        return Token(OPERATOR, self.text[start:self.pos])

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.text):
            self._skip_whitespace()
            if self.pos >= len(self.text):
                break
            char = self._current()
            if comment := self._skip_comment():
                self.tokens.append(comment)
                continue
            if char == "'":
                self.tokens.append(self._get_string())
                continue
            if char == '"':
                # Double-quote always starts a quoted identifier in PostgreSQL
                self.tokens.append(self._get_quoted_identifier())
                continue
            if char.isdigit() or (char == '.' and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit()):
                self.tokens.append(self._get_number())
                continue
            if char.isalpha() or char in {'_', '$'}:
                self.tokens.append(self._get_identifier())
                continue
            if char in SPEC_CHARS:
                self.tokens.append(Token(SPECIAL, char))
                self._advance()
                continue
            if char in ''.join(OPERATORS) or char in {'<', '>', '=', '!'}:
                self.tokens.append(self._get_operator())
                continue
            self.tokens.append(Token(UNKNOWN, char))
            self._advance()
        self.tokens.append(Token(EOF, ''))
        return self.tokens


class TableExtractor:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.tables: List[Tuple[str, str]] = []

    def extract_tables(self) -> List[Tuple[str, str]]:
        i = 0
        while i < len(self.tokens):
            tok = self.tokens[i]
            if tok.type == KOI and tok.value in TABLE_KOI:
                # Advance past the KOI token, then parse the table context.
                # _parse_table_context returns the index where it stopped so
                # the outer loop resumes correctly after the parsed clause —
                # previously the return value was ignored, causing i to never
                # advance past multi-table clauses (e.g. FROM a, b, c).
                i = self._parse_table_context(i + 1)
            else:
                i += 1
        return self.tables

    def _parse_table_context(self, i: int) -> int:
        """
        Parse one or more table references after a KOI token.
        Returns the index of the first token that belongs to the next clause,
        so the caller can resume the outer scan from there.
        """
        while i < len(self.tokens):
            tok = self.tokens[i]

            # Bail out on clause-ending keywords/tokens
            if tok.type == EOF:
                break
            if tok.type == KOI:
                break
            if tok.type == KEYWORD and tok.value in {
                'on', 'where', 'group', 'order', 'having', 'set',
                'select', 'insert', 'update', 'delete', 'create', 'drop', 'alter'
            }:
                break
            if tok.type == SPECIAL and tok.value in {'(', ')', ';'}:
                # Skip subquery open-paren; stop on close-paren or statement end
                if tok.value == '(':
                    i += 1
                    continue
                break

            # Comma separating multiple tables — skip and keep parsing
            if tok.type == SPECIAL and tok.value == ',':
                i += 1
                continue

            # Dot for schema-qualified names: consume schema.table as one identifier
            if tok.type == SPECIAL and tok.value == '.':
                # The previous table entry already has the schema part; replace
                # it with the fully qualified name, then consume any alias on
                # the same pass so it is not mistaken for a new table reference.
                i += 1
                if i < len(self.tokens) and self.tokens[i].type == IDENTIFIER:
                    if self.tables:
                        schema, old_alias = self.tables[-1]
                        fq_name = f"{schema}.{self.tokens[i].value}"
                        i += 1
                        alias = ''
                        # Optional AS keyword
                        if (i < len(self.tokens)
                                and self.tokens[i].type == KEYWORD
                                and self.tokens[i].value == 'as'):
                            i += 1
                        # Alias identifier
                        if (i < len(self.tokens)
                                and self.tokens[i].type == IDENTIFIER
                                and self.tokens[i].value not in SQL_KEYWORDS
                                and self.tokens[i].value not in TABLE_KOI):
                            alias = self.tokens[i].value
                            i += 1
                        self.tables[-1] = (fq_name, alias)
                continue

            if tok.type in {IDENTIFIER, CONSTANT}:
                table = tok.value.lower()
                alias = ''
                i += 1

                # Optional AS keyword
                if i < len(self.tokens) and self.tokens[i].type == KEYWORD and self.tokens[i].value == 'as':
                    i += 1

                # Alias: next token is an identifier that is not a keyword/KOI
                if (i < len(self.tokens)
                        and self.tokens[i].type == IDENTIFIER
                        and self.tokens[i].value not in SQL_KEYWORDS
                        and self.tokens[i].value not in TABLE_KOI):
                    alias = self.tokens[i].value
                    i += 1

                self.tables.append((table, alias))
                continue

            # Anything else (operators, etc.) — step over it
            i += 1

        return i


def get_sql_files(path: str) -> List[Tuple[str, str]]:
    path_obj = Path(path)
    files = []
    if path_obj.is_file():
        if path_obj.suffix.lower() in {'.sql', '.txt'}:
            try:
                with open(path_obj, encoding='utf-8', errors='ignore') as f:
                    files.append((str(path_obj), f.read()))
            except Exception as e:
                print(f"Warning: Could not read {path_obj}: {e}", file=sys.stderr)
    elif path_obj.is_dir():
        for root, _, filenames in os.walk(path_obj):
            for filename in filenames:
                if Path(filename).suffix.lower() in {'.sql', '.txt'}:
                    filepath = Path(root) / filename
                    try:
                        with open(filepath, encoding='utf-8', errors='ignore') as f:
                            files.append((str(filepath), f.read()))
                    except Exception as e:
                        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
    return files


def main():
    parser = argparse.ArgumentParser(description="SQL Tokenizer and Table Extractor")
    parser.add_argument("path", nargs="?", help="File, folder, or omitted with --text")
    parser.add_argument("-t", "--text", help="Direct SQL text")
    parser.add_argument("--tokens", action="store_true", help="Print all tokens")
    parser.add_argument("--tables", action="store_true", help="Print extracted tables (default when --search used)")
    parser.add_argument("--search", help="Filter to files referencing this table name (case-insensitive)")
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--output", help="Output file for JSON/CSV (optional)")

    args = parser.parse_args()

    if not args.path and not args.text:
        print("Error: Provide path or --text", file=sys.stderr)
        sys.exit(1)

    texts = []
    if args.text:
        texts.append(("input", args.text))
    elif args.path:
        texts = get_sql_files(args.path)
        if not texts:
            print(f"Error: No SQL files found in {args.path}", file=sys.stderr)
            sys.exit(1)

    results = []
    search_term = args.search.lower() if args.search else None
    match_count = 0

    show_tables = args.tables or bool(args.search) or bool(args.text)

    for name, sql in texts:
        tokenizer = Tokenizer(sql)
        tokens = tokenizer.tokenize()
        extractor = TableExtractor(tokens)
        tables = extractor.extract_tables()

        table_names = {table for table, _ in tables}

        if search_term and search_term not in table_names:
            continue

        if args.search:
            match_count += 1

        file_result = {
            "file": name,
            "tables": [{"table": t, "alias": a} for t, a in tables]
        }
        results.append(file_result)

        if args.format == "text":
            print(f"\n=== {name} ===")
            if args.tokens:
                for t in tokens:
                    if t.type != EOF:
                        print(t)
            if show_tables:
                print("Tables found:")
                for table, alias in tables:
                    print(f"  {table}" + (f" AS {alias}" if alias else ""))

    if args.format == "text":
        if args.search:
            print(f"\nFound in {match_count} files")
        else:
            print(f"\nProcessed {len(results)} files")

    if args.format in {"json", "csv"} or args.output:
        output_data = results
        out_path = args.output or f"table_results.{args.format}"
        try:
            if args.format == "json":
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2)
            elif args.format == "csv":
                with open(out_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["file", "table", "alias"])
                    for res in output_data:
                        for t in res["tables"]:
                            writer.writerow([res["file"], t["table"], t["alias"]])
            print(f"Results saved to {out_path}")
        except Exception as e:
            print(f"Error writing output: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()