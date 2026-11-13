# b109-eval-tasks

A collection of small, independent Python utility modules with unit tests.

- Python 3.12, standard library only.
- No network access is needed to run anything.

## Modules

All modules live in the `b109tasks` package.

| Module | What it does |
|---|---|
| `daterange` | Parse date ranges such as `2024-03`, `2024` or `2024-03-05..2024-03-09`, and work with the resulting inclusive ranges. |
| `configmerge` | Parse INI-like configuration text, merge several configs, resolve `${section.key}` references, and read typed values. |
| `ratelimit` | A token-bucket rate limiter with an injectable clock. |
| `csvreport` | Build CSV and markdown reports from rows of dicts, with per-column formats and totals. |
| `money` | A `Money` value type: Decimal amounts, currency checks, banker's rounding. |
| `template` | A tiny text template engine with variables, filters, `if` blocks and `for` loops. |
| `retry` | Retry a call with exponential backoff, an optional time budget and an optional rate limiter; sleep and clock are injectable. |
| `archive` | List zip archive contents, refusing archives with unsafe member paths. |
| `lru` | A least-recently-used cache with hit/miss statistics. |
| `semver` | Semantic version parsing, ordering and range matching. |
| `mdtable` | Format rows as an aligned markdown table. |
| `scheduler` | Order and run jobs with dependencies, retries and time budgets, detecting cycles. |

Each module's docstring describes its behaviour in more detail.

## Running the tests

    bash check.sh

This runs `python3 -m unittest discover -s tests -v` and exits non-zero if any
test fails. CI runs the same script on every push.
