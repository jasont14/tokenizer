#!/usr/bin/env python3
"""
Simple SQL Tokenizer and Table Extractor for PostgreSQL.
Hand-rolled lexer (no regex).
"""

import os
import sys
import argparse
from typing import List, Tuple

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
        quote = self._current()
        start = self.pos
        self._advance()
        while self._current() is not None:
            if self._current() == quote:
                self._advance()
                break
            if self._current() == '\\':
                self._advance()
            self._advance()
        return Token(CONSTANT, self.text[start:self.pos])

    def _get_number(self):
        start = self.pos
        while self._current() is not None and (self._current().isdigit() or self._current() in {'.', 'e', 'E', '+', '-'}):
            self._advance()
        return Token(CONSTANT, self.text[start:self.pos])

    def _get_identifier(self):
        start = self.pos
        while self._current() is not None and (self._current().isalnum() or self._current() in {'_', '"', '$'}):
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
            if char in {"'", '"'}:
                self.tokens.append(self._get_string())
                continue
            if char.isdigit() or (char == '.' and self.pos + 1 < len(self.text) and self.text[self.pos + 1].isdigit()):
                self.tokens.append(self._get_number())
                continue
            if char.isalpha() or char in {'_', '"', '$'}:
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
        self.tables = []

    def extract_tables(self) -> List[Tuple[str, str]]:
        i = 0
        while i < len(self.tokens):
            tok = self.tokens[i]
            if tok.type == KOI and tok.value in TABLE_KOI:
                i += 1
                self._parse_table_context(i)
                while i < len(self.tokens) and self.tokens[i].type not in {KEYWORD, KOI, SPECIAL, EOF}:
                    i += 1
                continue
            i += 1
        return self.tables

    def _parse_table_context(self, i: int):
        while i < len(self.tokens):
            tok = self.tokens[i]
            if tok.type in {KEYWORD, KOI, SPECIAL, EOF} and tok.value not in {'as', '.'}:
                if tok.value in {'on', 'where', 'group', 'order'}:
                    break
                if tok.value == ',':
                    i += 1
                    continue
                break

            if tok.type in {IDENTIFIER, CONSTANT}:
                table = tok.value
                alias = ''
                i += 1
                if i < len(self.tokens) and self.tokens[i].value == 'as':
                    i += 1
                if i < len(self.tokens) and self.tokens[i].type == IDENTIFIER:
                    alias = self.tokens[i].value
                    i += 1
                self.tables.append((table, alias))
            else:
                i += 1


def main():
    parser = argparse.ArgumentParser(description="SQL Tokenizer and Table Extractor")
    parser.add_argument("path", nargs="?", help="File or folder")
    parser.add_argument("-t", "--text", help="Direct SQL text")
    parser.add_argument("--tokens", action="store_true")
    parser.add_argument("--tables", action="store_true")
    args = parser.parse_args()

    if not args.path and not args.text:
        print("Error: Provide path or --text", file=sys.stderr)
        sys.exit(1)

    texts = []
    if args.text:
        texts.append(("input", args.text))
    elif os.path.isfile(args.path or ""):
        with open(args.path, encoding='utf-8') as f:
            texts.append((args.path, f.read()))

    for name, sql in texts:
        print(f"\n=== {name} ===")
        tokenizer = Tokenizer(sql)
        tokens = tokenizer.tokenize()

        if args.tokens:
            for t in tokens:
                if t.type != EOF:
                    print(t)

        extractor = TableExtractor(tokens)
        tables = extractor.extract_tables()
        print("Tables found:")
        for table, alias in tables:
            print(f"  {table}" + (f" AS {alias}" if alias else ""))


if __name__ == "__main__":
    main()