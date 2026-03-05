# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running Tests
```bash
# All tests
source .venv/bin/activate && python -m pytest tests/ -v

# Single test file
source .venv/bin/activate && python -m pytest tests/test_bot.py -v

# Single test
source .venv/bin/activate && python -m pytest tests/test_bot.py::TestClassName::test_method_name -v

# Exclude slow tests
source .venv/bin/activate && python -m pytest tests/ -m "not slow" -v
```

**Critical:** Always use `.venv/` — the venv at `.venv/` must be active for all Python operations.

### Running the Bot
```bash
source .venv/bin/activate && python main.py
```

Requires a `.env` file (or environment variables) with at minimum `DISCORD_TOKEN` and `CHANNEL_IDS`.

### Dynamic Log Level Change (no restart needed)
```bash
echo "DEBUG" > /tmp/chatd_loglevel && kill -HUP <pid>
```

## Architecture

### Startup Flow
`main.py` → `setup_logging()` → `validate_config()` → `run_bot()`

Config is a singleton (`chatd/config.py`) loaded from environment variables / `.env`. Validation runs a live Discord connection test and a `git ls-remote` check, so startup requires network access.

### Core Polling Loop (`chatd/bot.py`)
Every `CHECK_INTERVAL_MINUTES` minutes the bot:
1. Calls `clone_or_update_repo()` — git pull; returns `True` only when `listings.json` changes
2. Reads `listings.json` via `read_json()`
3. Calls `storage.detect_job_changes()` to diff current vs. stored jobs
4. Posts new/updated jobs to Discord channels using a `heapq` priority queue (chronological by `date_posted`)
5. Adds reactions via `ReactionQueue` — a background `asyncio.Queue` with failure classification, health monitoring, and a circuit breaker

### Storage Abstraction (`chatd/storage_abstraction.py`)
Three modes controlled by `MIGRATION_MODE` env var:
- `json_only` — flat JSON files only (default; no DB required)
- `dual_write` — writes to both JSON and PostgreSQL simultaneously
- `database_only` — PostgreSQL only

`DataStorage` wraps `StorageBackend` implementations. For tests, use `MockDataStorage` from `tests/mock_datastorage.py`.

**Soft delete**: Jobs are marked `is_deleted=True` rather than removed, preserving Discord message/reaction references. The "job resurrection" feature revives soft-deleted jobs if they reappear upstream.

### Database Models (`chatd/database.py`)
SQLAlchemy 2 ORM against PostgreSQL 15. Key tables:
- `job_postings` — core job data; compound index on `(active, is_visible, is_deleted)`
- `job_locations`, `job_terms`, `job_degrees` — normalized one-to-many children with CASCADE delete
- `message_tracking` — maps job → Discord message ID + channel ID (one-to-one)
- `student_applications` — tracks which users reacted with the apply emoji

### Reaction System (`chatd/bot.py` — `ReactionQueue`)
Reactions are queued asynchronously to avoid blocking the main event loop. The queue classifies failures (`RATE_LIMITED`, `PERMANENT_ERROR`, `SERVER_ERROR`, etc.) and applies different retry strategies. A circuit breaker trips after `CIRCUIT_BREAKER_THRESHOLD` consecutive failures.

Two special reactions drive interactivity (configurable via `MESSAGE_REACTIONS`):
- `INFO_REACTION_EMOJI` (default `❓`) — triggers a DM with company info
- `APPLICATION_REACTION_EMOJI` (default `📝`) — tracks the user's application and sends a congratulatory DM with a random tip

## Git Workflow

- **Never push directly to `main`** — use feature branches and pull requests
- Branch naming: `feature/description`, `bugfix/description`, `docs/description`, `refactor/description`
- Always verify current branch before committing: `git branch` or `git status`

## Test Conventions

- `pytest.ini` sets `asyncio_mode = strict` — async tests must be decorated with `@pytest.mark.asyncio`
- Mock config with `create_mock_config()` from `tests/mock_datastorage.py`; it pre-fills all config attributes tests typically need
- When adding config attributes to `Config`, also add them to `create_mock_config()` to avoid `AttributeError` in tests
- External dependencies (Discord API, filesystem, database) should be mocked in unit tests
