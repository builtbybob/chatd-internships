# Ch@d Internships — Development Guide

This guide covers everything needed to set up a local development environment, run and write tests, and understand the coding conventions used in this project.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Setup](#local-setup)
3. [Environment Configuration](#environment-configuration)
4. [Running the Bot Locally](#running-the-bot-locally)
5. [Testing](#testing)
6. [Code Conventions](#code-conventions)
7. [Adding New Features](#adding-new-features)
8. [Debugging](#debugging)
9. [Common Development Tasks](#common-development-tasks)

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime (3.11 used in Dockerfile) |
| Git | Any | Repository management |
| PostgreSQL | 15+ | Database backend (optional for `json_only` dev) |
| Docker + Compose | V2 | Full-stack local environment |

---

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/builtbybob/chatd-internships.git
cd chatd-internships

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Copy the example environment file

```bash
cp examples/.env.example .env
```

Edit `.env` with your values. At minimum you need `DISCORD_TOKEN` and `CHANNEL_IDS`. See [Environment Configuration](#environment-configuration) for all options.

### 3. (Optional) Start a local PostgreSQL instance with Docker

```bash
docker compose up -d chatd-postgres
```

Or point `DB_HOST` at any running PostgreSQL 15+ instance.

---

## Environment Configuration

All configuration is via environment variables (loaded from `.env` by `python-dotenv`). The `Config` singleton in `chatd/config.py` handles parsing and validation.

### Required

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Bot token from Discord Developer Portal |
| `CHANNEL_IDS` | Comma-separated Discord channel IDs (snowflakes) |

### Storage mode

| Variable | Default | Options |
|---|---|---|
| `MIGRATION_MODE` | `json_only` | `json_only`, `dual_write`, `database_only` |

Use `json_only` for development if you don't want to run PostgreSQL. Use `database_only` in production.

### PostgreSQL (when `MIGRATION_MODE != json_only`)

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `chatd-postgres` | Hostname |
| `DB_PORT` | `5432` | Port |
| `DB_NAME` | `chatd` | Database name |
| `DB_USER` | `chatd` | Username |
| `DB_PASSWORD` | _(required)_ | Password |

### Bot behaviour

| Variable | Default | Description |
|---|---|---|
| `CHECK_INTERVAL_MINUTES` | `1` | Polling frequency (1–60) |
| `MAX_POST_AGE_DAYS` | `5` | Skip listings older than this many days |
| `ENABLE_REACTIONS` | `false` | Add emoji reactions to posted messages |
| `MESSAGE_REACTIONS` | `❓,📝` | Comma-separated reaction emojis |
| `ENABLE_COMPANY_INFO` | `true` | ❓ reaction triggers company info DM |
| `ENABLE_APPLICATION_TRACKING` | `true` | 📝 reaction tracks application |
| `ABORT_ON_EMPTY_STORAGE` | `true` | Abort diff if no previous state (prevents re-posting everything after wipe) |
| `ENABLE_GENERIC_TITLES` | `true` | Generate fallback titles for blank job titles |
| `GENERIC_JOB_TITLE` | `Intern` | Base word for generated titles (e.g. "Intern - AI/ML") |

### Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FILE` | `/app/logs/chatd.log` | File path; directory is created if missing |
| `LOG_MAX_BYTES` | `10485760` | Rotate at this size (10 MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated backups to keep |

---

## Running the Bot Locally

```bash
source .venv/bin/activate
python main.py
```

**Startup sequence you should see:**

```
[INFO] Logging configured with level: INFO
[INFO] Starting ChatD Internships Bot...
[INFO] Validating configuration...
[INFO] Configuration validation passed.
[INFO] Starting Discord bot...
[INFO] Logged in as YourBot#1234
[INFO] Bot is ready and monitoring 1 channel(s)
```

If the listings file has not changed since the last run, you will see:
```
[DEBUG] Repository pulled but listings file unchanged.
```

This is correct — it means the bot detected no changes and skipped posting.

---

## Testing

### Running the test suite

```bash
source .venv/bin/activate

# All tests
python -m unittest discover tests/

# Specific module
python -m unittest tests.test_messages
python -m unittest tests.test_config
python -m unittest tests.test_storage_abstraction

# Verbose output
python -m unittest discover tests/ -v

# Via pytest (also configured)
pytest
pytest tests/test_messages.py -v
```

### Test organisation

| Test file | What it covers |
|---|---|
| `test_bot.py` | Discord bot event handlers, reaction dispatch |
| `test_config.py` | Config parsing, validation logic |
| `test_database_models.py` | SQLAlchemy ORM models, relationships, constraints |
| `test_storage_abstraction.py` | Multi-backend storage operations and migration modes |
| `test_migration.py` | JSON → database migration validation and rollback |
| `test_update_support.py` | Differential update workflows, change detection |
| `test_validation.py` | Data integrity and constraint validation |
| `test_messages.py` | `format_message()`, `compare_roles()`, epoch formatting |
| `test_repo.py` | Repository clone/pull logic |
| `test_soft_delete.py` | Soft-delete behaviour |
| `test_resurrection.py` | Job resurrection (soft-deleted job reappears upstream) |
| `test_application_tracking.py` | Student application tracking |
| `test_configurable_reactions.py` | Reaction configuration |
| `test_reaction_batching.py` | ReactionQueue batching and rate limiting |
| `test_message_optimization.py` | Message posting delay / ordering |
| `test_storage.py` | Legacy `FileStorage` |
| `test_bug_simulation.py` | Regression simulations |
| `test_integration.py` | End-to-end integration tests |

### Mock objects

`tests/mock_datastorage.py` provides `MockDataStorage`, a `DataStorage` substitute that stores state in memory. Use this in any test that touches storage logic to avoid filesystem or database dependencies.

### Async tests

Tests of async functions use `pytest-asyncio` in strict mode (configured in `pytest.ini`). Mark async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_something_async():
    ...
```

---

## Code Conventions

### Style

- PEP 8 (no enforced linter configured, but the codebase follows it)
- Type hints on public function signatures (`from typing import List, Dict, Any, Optional`)
- Module-level docstrings on every file
- Function/method docstrings using Google style (Args / Returns sections)

### Logging

Use `logger = logging.getLogger(__name__)` at module level. Never print to stdout — always log.

| Level | When to use |
|---|---|
| `DEBUG` | Per-iteration detail, git hashes, file reads |
| `INFO` | Lifecycle events: startup, shutdown, new jobs posted |
| `WARNING` | Recoverable issues: channel not found, git timeout |
| `ERROR` | Failed operations that affect functionality |
| `CRITICAL` | Should not occur — fatal, unrecoverable |

### Error handling

- Catch specific exceptions, not bare `except Exception`
- Always log the exception before re-raising or returning a default
- Return `bool` success flags from storage operations rather than raising (callers can decide)
- Let `bot.py` catch and log Discord API errors; the loop continues

### Configuration access

Import `from chatd.config import config` and access attributes (`config.max_retries`, etc.). Do not read `os.getenv()` directly in non-config modules.

### Database sessions

Always use the context manager:

```python
with db_manager.session_scope() as session:
    # query / insert / update
    pass  # auto-commit on exit, rollback on exception
```

Never call `session.commit()` manually inside the block.

---

## Adding New Features

### Adding a new configuration option

1. Add the default value to `DEFAULT_CONFIG` in `chatd/config.py`
2. Add type conversion in `Config.__init__()` if needed (int, float, bool)
3. Add validation in `Config.validate()` or a new `_validate_*` method
4. Add a test in `tests/test_config.py`
5. Document in `examples/.env.example`

### Adding a new reaction handler

1. Add the emoji to `MESSAGE_REACTIONS` default and documentation
2. In `bot.py:on_raw_reaction_add`, add an `elif emoji_name == 'your_emoji':` branch
3. Implement `async def handle_your_reaction(self, payload, job):`
4. Add tests in `tests/test_configurable_reactions.py`

### Adding a new storage operation

1. Add the abstract method to `StorageBackend` in `storage_abstraction.py`
2. Implement in both `JsonStorageBackend` and `DatabaseStorageBackend`
3. Expose via `DataStorage` (the facade), routing to active backend(s)
4. Add tests in `tests/test_storage_abstraction.py`

### Adding a new database column

1. Add the `Column` to the appropriate ORM model in `database.py`
2. Create a migration SQL file in `sql/migrations/` following the `VN__description.sql` naming convention
3. Update `job_posting_from_dict()` and `job_posting_to_dict()` if needed
4. Update the JSON backend to handle the new field
5. Add tests

---

## Debugging

### Enable verbose logging

```bash
LOG_LEVEL=DEBUG python main.py
```

Or at runtime without restarting (production):
```bash
echo "DEBUG" > /tmp/chatd_loglevel && kill -HUP $(pgrep -f main.py)
```

### Inspect the database directly

```bash
# Docker environment
docker exec -it chatd-postgres psql -U chatd -d chatd

# Direct psql
psql postgresql://chatd:password@localhost:5432/chatd
```

Useful queries:

```sql
-- All jobs, newest first
SELECT id, company_name, title, active, is_deleted
FROM job_postings ORDER BY date_posted DESC LIMIT 20;

-- Jobs with their Discord messages
SELECT jp.company_name, jp.title, mt.message_id, mt.channel_id, mt.posted_at
FROM job_postings jp
JOIN message_tracking mt ON jp.id = mt.id
ORDER BY mt.posted_at DESC LIMIT 10;

-- Soft-deleted jobs
SELECT company_name, title, is_deleted FROM job_postings WHERE is_deleted = true;
```

### Force a re-check

The bot only processes when `listings.json` changes. To force processing during development, temporarily touch the file or manually set `was_updated = True` in `repo.py`.

### Test a specific message format

```python
from chatd.messages import format_message

role = {
    'company_name': 'Acme Corp',
    'title': 'Software Engineering Intern',
    'url': 'https://example.com/apply',
    'locations': ['New York, NY', 'Remote'],
    'terms': ['Summer 2026'],
    'sponsorship': 'Does not sponsor',
    'date_posted': 1706745600,
}
print(format_message(role))
```

---

## Common Development Tasks

### Migrate JSON data to the database

```bash
# Start with dual_write mode
export MIGRATION_MODE=dual_write

# Run migration (populates DB from JSON)
python scripts/migrate_json_to_database.py

# Validate consistency
python scripts/migrate_json_to_database.py --validate

# Switch to database_only
export MIGRATION_MODE=database_only
```

### Reset the bot's state (re-post all jobs)

**Warning**: this will cause the bot to re-post every job from scratch.

For JSON mode: delete `data/previous_data.json` and `data/message_tracking.json`.

For database mode: truncate the relevant tables:
```sql
TRUNCATE message_tracking;
TRUNCATE job_postings CASCADE;  -- also removes locations/terms/degrees
```

### Sync repo data to a specific commit (for testing)

```bash
# Replay the bot against a specific upstream commit
sudo ./scripts/sync-repo-data.sh abc123def456
```

### Check storage health

```python
from chatd.config import load_config
from chatd.storage_abstraction import DataStorage

config = load_config()
storage = DataStorage(config)
print(storage.get_backend_status())
print(storage.health_check())
```
