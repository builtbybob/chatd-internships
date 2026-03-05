# Contributing to Ch@d Internships

Thank you for considering a contribution! This document covers how to report issues, propose changes, and get code merged.

---

## Table of Contents

1. [Reporting Issues](#reporting-issues)
2. [Development Workflow](#development-workflow)
3. [Pull Request Guidelines](#pull-request-guidelines)
4. [Testing Requirements](#testing-requirements)
5. [Code Review Checklist](#code-review-checklist)

---

## Reporting Issues

Before opening an issue:
- Check existing issues to avoid duplicates
- Collect relevant log output (use `chatd logs --tail=100` or check `/opt/<env>/logs/chatd.log`)
- Note your `MIGRATION_MODE`, Python version, and whether you're running Docker or local

**Include in bug reports:**
- Steps to reproduce
- Expected vs actual behaviour
- Log snippet (sanitise tokens/passwords before sharing)
- Python version (`python --version`) and relevant dependencies (`pip show discord.py sqlalchemy`)

---

## Development Workflow

### 1. Fork and branch

```bash
git checkout -b feature/my-feature   # or bugfix/description
```

Branch naming conventions:
- `feature/<short-description>` — new functionality
- `bugfix/<short-description>` — bug fix
- `refactor/<short-description>` — code restructuring without behaviour change

### 2. Set up your environment

Follow [DEVELOPMENT.md](DEVELOPMENT.md) to get a working local environment with tests passing.

### 3. Make your changes

- Keep changes focused — one feature or fix per PR
- Follow the [code conventions](DEVELOPMENT.md#code-conventions) in DEVELOPMENT.md
- Add or update tests for any changed behaviour (see [Testing Requirements](#testing-requirements))

### 4. Verify locally

```bash
# All tests must pass
python -m unittest discover tests/ -v

# Confirm no obvious import errors
python -c "from chatd import bot, config, database, messages, repo, storage_abstraction"

# If touching database schema — test with a fresh database
docker compose down -v && docker compose up -d chatd-postgres
python -c "
from chatd.config import config
from chatd.database import create_database_manager
db = create_database_manager(config)
db.create_tables()
print('Schema OK')
"
```

### 5. Open the pull request

Push your branch and open a PR against `main`. Fill in the PR template with a summary of what changed and why.

---

## Pull Request Guidelines

### What makes a good PR

- **Small and focused** — easier to review, less risk of introducing bugs
- **Includes tests** — new behaviour is verified; regressions are caught
- **Updates documentation** — if you changed a config option, update `examples/.env.example` and the relevant `.md` file
- **Clear commit messages** — describe *why*, not just *what*

### What to expect

- A maintainer will review within a few days
- You may be asked to revise before merge
- CI must pass (test coverage workflow on GitHub Actions)

---

## Testing Requirements

Every PR that changes logic **must** include corresponding tests.

| Change type | Required tests |
|---|---|
| New config option | `tests/test_config.py` — default value, parsing, validation |
| New storage operation | `tests/test_storage_abstraction.py` — both JSON and DB backends |
| New reaction handler | `tests/test_configurable_reactions.py` |
| New message format | `tests/test_messages.py` |
| Bug fix | Regression test that would have caught the original bug |
| Database schema change | `tests/test_database_models.py` — model constraints, relationships |

### Test quality expectations

- Tests should be **independent** — no shared mutable state between test methods
- Use `MockDataStorage` from `tests/mock_datastorage.py` rather than real filesystem or database in unit tests
- Async Discord handlers: use `unittest.mock.AsyncMock` for Discord API calls
- No hardcoded secrets, tokens, or IDs in test code

---

## Code Review Checklist

Before requesting review, confirm:

- [ ] All existing tests pass (`python -m unittest discover tests/`)
- [ ] New tests cover the changed logic
- [ ] No secrets, tokens, or personal data in the diff
- [ ] Logging added for significant operations (`logger.info / debug / error`)
- [ ] Config options documented in `examples/.env.example`
- [ ] Database schema changes have a migration file in `sql/migrations/`
- [ ] Both storage backends (`JsonStorageBackend` and `DatabaseStorageBackend`) handle new operations if applicable
- [ ] `is_deleted` filter is applied correctly in any new database queries (exclude soft-deleted jobs except for Discord reaction lookups)
- [ ] Error cases handled and logged — no silent failures
- [ ] No `print()` statements — use `logger`
