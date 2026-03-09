# Test Layout

This project uses `pytest` with a split between unit and integration tests.

## Structure

- `tests/unittest/`: pure unit tests (no DB, no HTTP).
- `tests/integration/`: tests that use Flask app, routes, DB, or external boundaries.
- `tests/templates/`: copy-paste starters for new tests.
- `tests/conftest.py`: shared fixtures (`app`, `client`, `db_session`).

## Run

```bash
pytest
pytest -m unittest
pytest -m integration
```

## Notes

- Integration tests use the `testing` config and a test SQLite database URL via `TEST_DATABASE_URL`.
- `db_session` resets schema per test for isolation.
