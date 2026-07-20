# SQL Table Extractor & Tokenizer

A simple, fast, hand-rolled SQL tokenizer and table extractor for PostgreSQL (and similar dialects).

**Primary use case**: Quickly scan large collections of SQL files (DML, queries, scripts) to find references to specific tables — especially useful when refactoring, auditing dependencies, or migrating schemas.

## Features

- Tokenizes SQL without external dependencies (pure Python, no regex-heavy parsing)
- Extracts tables from `FROM`, `JOIN`, `INTO`, `WITH` clauses (with optional aliases)
- **Recursive folder scanning** — handles deeply nested directories
- `--search TABLE_NAME` — filter files that reference a specific table
- Summary statistics ("Found in X files")
- Output options: plain text, **JSON**, or **CSV** for easy analysis
- Works with single files, folders, or direct `--text`
- Robust file handling (UTF-8, skips unreadable files gracefully)

## Usage Examples

### Search for a table across many files
```bash
python3 Tokenize.PY ./queries_folder/ --search customer_master
```

**Sample output:**
```
=== ./queries_folder/sales.sql ===
Tables found:
  customer_master
  orders AS o

=== ./queries_folder/reports/monthly.sql ===
Tables found:
  customer_master AS cm

Found in 47 files
```

### Direct text (great for quick testing)
```bash
python3 Tokenize.PY --text "SELECT * FROM users u JOIN orders o ON u.id = o.user_id"
```

### Export for analysis
```bash
# JSON
python3 Tokenize.PY ./queries_folder/ --search customer_master --format json --output results.json

# CSV (flat table list)
python3 Tokenize.PY ./queries_folder/ --format csv --output all_tables.csv
```

### Other flags
- `--tables` — always show extracted tables
- `--tokens` — debug the full token stream
- `--output FILE` — save JSON/CSV to a specific path

## Real-World Usage

This utility was used to scan **over 500 DML SQL files** spread across multiple folders and nested subdirectories. It successfully identified references to specific tables, making dependency analysis and refactoring significantly faster.

## Installation

No extra packages required — just Python 3.6+.

```bash
# Make executable (optional)
chmod +x Tokenize.PY
```

## Limitations

- Hand-rolled parser focused on common PostgreSQL patterns
- Best-effort alias and complex join detection
- Does not deeply parse subqueries or CTEs in every edge case (but works well for typical DML)

## Contributing / Extending

Feel free to improve the lexer or add support for more SQL dialects.

---

**Made for efficient SQL codebase archaeology.**
