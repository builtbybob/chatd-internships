# Code Audit Report — chatd-internships

> Generated: 2026-02-28

## Executive Summary

**Overall Health: Good (7/10)** — This is a well-structured, production-grade Discord bot with solid test coverage and thoughtful architecture. The main concerns are code organization (two large monolith files), a few reliability risks in the database layer, and a handful of code quality issues that compound maintenance burden over time.

| Category | Score | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| Architecture & Design | 7/10 | 0 | 2 | 2 | 1 |
| Code Quality | 6/10 | 0 | 2 | 4 | 3 |
| Security | 9/10 | 0 | 0 | 1 | 1 |
| Performance | 7/10 | 0 | 1 | 2 | 1 |
| Testing | 8/10 | 0 | 0 | 2 | 1 |
| Maintainability | 7/10 | 0 | 1 | 2 | 2 |

**Top 3 priorities:**
1. Add `pool_pre_ping=True` to SQLAlchemy engine (will cause silent connection failures in production)
2. Deduplicate `detect_job_changes` (3 near-identical copies)
3. Split `bot.py` (1,851 lines) into focused modules

---

## Findings by Category

### Architecture & Design

#### 🔴 High Priority

**`bot.py` is a 1,851-line monolith** (`chatd/bot.py`)
- Contains: `ReactionQueue` class, all Discord event handlers, polling loop, DM logic, company info, application tracking, channel management, and the scheduler bridge. Everything in one file.
- Impact: Any change to one area requires reading ~600 lines of unrelated code. Merges conflict frequently. Hard to onboard new contributors.
- Recommendation: Split into `reaction_queue.py`, `event_handlers.py`, `dm_handlers.py`, and keep `bot.py` as a thin coordinator. Estimated effort: 2–3 days.

**`detect_job_changes` duplicated 3 times** (`chatd/storage_abstraction.py:230, 615, 1010`)
- The `JsonStorageBackend` and `DatabaseStorageBackend` versions are byte-for-byte identical except for the debug log message. The `DataStorage.detect_job_changes` (line 1010) has a different signature (`previous_jobs` is omitted — it loads from storage).
- Impact: A bug fix or field addition must be applied in 3 places. This has already diverged (DB version logs `"Database change detection:"`, JSON version logs `"Change detection:"`).
- Recommendation: Extract a `_detect_changes_between(current, previous)` free function; both backends delegate to it. Effort: 1 hour.

#### 🟡 Medium Priority

**`schedule` library mixing sync with async** (`chatd/bot.py:1594–1621, 1794`)
- `schedule` is a synchronous scheduler. It's driven by a `while True: schedule.run_pending(); await asyncio.sleep(1)` loop inside `on_ready`. The bridge (`run_check_for_new_roles`) creates an async task via the deprecated `bot.loop.create_task()`.
- Impact: If `schedule.run_pending()` takes longer than 1 second (unlikely but possible), it blocks the event loop. The `bot.loop` access is deprecated in discord.py 2.x.
- Recommendation: Replace with `discord.ext.tasks.loop` which is native async and integrates cleanly with discord.py. Effort: 2 hours.

**Legacy `storage.py` still maintained** (`chatd/storage.py`, 228 lines)
- Described as deprecated but still imported by `tests/test_integration.py:399`. Any future change to the storage interface may need to update this file too.
- Impact: Maintenance surface without production value.
- Recommendation: Remove `storage.py` and update the one test that imports it. Effort: 30 minutes.

#### 🟢 Low Priority

**`storage_abstraction.py` at 1,478 lines** — should be split into `json_backend.py` and `database_backend.py` with a thin `data_storage.py` facade. Not urgent but will compound as features are added.

---

### Code Quality

#### 🔴 High Priority

**Bare `except:` in `messages.py:62`**
```python
except:
    target_tz = ZoneInfo('America/New_York')  # Final fallback
```
- Impact: Catches `KeyboardInterrupt`, `SystemExit`, `MemoryError`. If `ZoneInfo` construction itself fails (e.g., unknown timezone key), the exception is silently swallowed.
- Recommendation: Change to `except (KeyError, ValueError, ImportError):` or at minimum `except Exception:`. Effort: 1 minute.

**69 broad `except Exception` catches** (throughout `chatd/bot.py`, `chatd/storage_abstraction.py`)
- Most catch `Exception as e` then log and return `None`/`False`. This is often correct for a resilient bot, but ~15 of these in `bot.py` swallow the full traceback.
- Recommendation: For the handlers that use `logger.error(f"...: {e}")` without `exc_info=True`, add `exc_info=True` to preserve stack traces. Critical for diagnosing rare bugs. Effort: 30 minutes.

#### 🟡 Medium Priority

**Wrong log level for change detection diagnostic** (`chatd/storage_abstraction.py:1024`)
```python
logger.info(f"Change detection: {len(current_jobs)} current jobs vs {len(previous_jobs)} previous jobs")
```
- This fires on every polling cycle (default: every 1 minute) and logs at INFO. At production scale with INFO level, this generates 60 log lines/hour of noise.
- Recommendation: Change to `logger.debug`. Effort: 1 minute.

**`tuple[bool, bool]` uses Python 3.10+ syntax** (`chatd/storage_abstraction.py:387`)
```python
def add_job_posting(self, job_data: Dict[str, Any]) -> tuple[bool, bool]:
```
- The codebase uses a Python 3.9 fallback for `zoneinfo` (`messages.py:9–13`), implying 3.9 support is intended. Lowercase `tuple[...]` as a return type requires Python 3.10+.
- Recommendation: Change to `Tuple[bool, bool]` from `typing`. Effort: 1 minute.

**`channel_failure_counts` dict never pruned** (`chatd/bot.py:650–688`)
- Successful sends delete the count (`del channel_failure_counts[channel_id]`) but failed channels get added to `failed_channels` set permanently for the bot's lifetime. A channel that fails then gets fixed requires a bot restart.
- Recommendation: Add a periodic reset or a `!reset_channel <id>` command. Effort: 30 minutes.

**`run_check_for_new_roles` uses deprecated `bot.loop`** (`chatd/bot.py:1786`)
```python
if bot.loop and bot.loop.is_running():
    bot.loop.create_task(check_for_new_roles())
```
- `Client.loop` is deprecated in discord.py 2.0+ and will be removed. Should use `asyncio.get_event_loop()` or preferably switch to `discord.ext.tasks`.
- Recommendation: Replace with `discord.ext.tasks` loop. Effort: 1 hour (combined with schedule fix above).

#### 🟢 Low Priority

- `storage.py` re-exports an `ABC` class `Storage` and `FileStorage` which duplicate naming with `StorageBackend` — confusing to readers.
- The `# DEBUG: Log what we're comparing` comment at `storage_abstraction.py:1023` should be removed if the `logger.info` is changed to `logger.debug`.
- Some docstrings use both `Args:` and raw parameter descriptions inconsistently across `bot.py`.

---

### Security

#### 🟡 Medium Priority

**TOCTOU race condition in SIGHUP handler** (`chatd/logging_utils.py:~160`)
```python
if os.path.exists(level_file):
    with open(level_file, 'r') as f:
        new_level = f.read().strip().upper()
    os.remove(level_file)
```
- The check (`os.path.exists`) and use (`open`) are two separate operations. Another process could write to the file between them. Low severity since `/tmp/chatd_loglevel` is a local admin tool, not user-facing.
- Recommendation: Use `try/except FileNotFoundError` around the `open()` call instead of pre-checking existence. Effort: 2 minutes.

#### 🟢 Low Priority

- No `.gitignore` entries confirmed for `.env` files — worth verifying.
- The bot token validation only checks length (50+ chars) and contains `.`. While adequate as a sanity check, it doesn't prevent accidentally using an expired token (caught later at connection validation).

---

### Performance

#### 🔴 High Priority

**No `pool_pre_ping` on SQLAlchemy engine** (`chatd/database.py:159`)
```python
self.engine = create_engine(database_url, echo=echo)
```
- Without `pool_pre_ping=True`, connections cached in the pool are not tested before use. After periods of inactivity (e.g., overnight) PostgreSQL will close idle connections server-side; the next query will fail with `OperationalError: server closed the connection unexpectedly`.
- Impact: Silent failures at the exact moment the first user of the morning hits the bot. The `session_scope` context manager will catch and rollback, but the job won't be processed.
- Recommendation:
  ```python
  self.engine = create_engine(
      database_url, echo=echo,
      pool_pre_ping=True,
      pool_recycle=3600,
  )
  ```
  Effort: 5 minutes.

#### 🟡 Medium Priority

**3 separate queries inside `update_job_posting_with_refresh`** (`chatd/storage_abstraction.py:1371, 1403, 1435`)
```python
existing_locations = {loc.location for loc in session.query(JobLocation).filter(...)}
# ... later
existing_terms = {term.term for term in session.query(JobTerm).filter(...)}
# ... later
existing_degrees = {deg.degree for deg in session.query(JobDegree).filter(...)}
```
- This is called for every content-corrected job. Each call makes 3+ SELECT queries against the DB.
- Impact: Low severity at current scale (job updates are infrequent), but grows with job volume.
- Recommendation: Add `joinedload` or `subqueryload` to the parent query to eager-load relationships. Alternatively, use the already-defined `JobPosting.location_list`, `term_list`, `degree_list` properties. Effort: 30 minutes.

**`schedule` busy-poll loop** (`chatd/bot.py:1621`)
```python
await asyncio.sleep(1)  # Small delay to prevent busy-waiting
```
- This wakes up every second just to call `schedule.run_pending()`. With `CHECK_INTERVAL_MINUTES=1`, this means 59 wasted wakeups per cycle.
- Impact: Negligible on modern hardware, but `discord.ext.tasks` would fire exactly at the interval without any busy loop. Combined fix with the schedule→discord.ext.tasks migration above.

#### 🟢 Low Priority

- No `pool_recycle` set — long-lived connections can accumulate state (mentioned above, addressed by the `pool_pre_ping` fix).
- The `heapq` priority queue in the posting logic is correct and efficient.

---

### Testing

#### 🟡 Medium Priority

**Tests require explicit venv activation** — `python3 -m pytest` fails without activating `.venv/`. CI pipelines and new contributors need to know the exact invocation. The `README` / `docs/DEVELOPMENT.md` should document this explicitly.

**`test_integration.py` imports deprecated `chatd.storage`** (`tests/test_integration.py:399`)
```python
from chatd.storage import get_storage
```
- If `storage.py` is removed (recommended), this test silently breaks.
- Recommendation: Update to use `chatd.storage_abstraction.DataStorage`. Effort: 15 minutes.

#### 🟢 Low Priority

- No coverage measurement configured (`pytest-cov` not in `requirements.txt`). The 2.4x test-to-code line ratio suggests good coverage, but it's unverified.
- `test_bug_simulation.py` intentionally introduces a bug to test detection — the `# BUG: dirname shouldn't be used here` comment is a regression test pattern. Worth adding a note that this is intentional to avoid future confusion.

---

### Maintainability

#### 🔴 High Priority

**No separation of concerns in `bot.py`** (discussed in Architecture above) — Beyond size, the file mixes three distinct domains: infrastructure (`ReactionQueue`), Discord events, and business logic (application tracking, DM formatting). Any newcomer reading `bot.py` needs to understand all three simultaneously.

#### 🟡 Medium Priority

**Module-level globals with side effects** (`chatd/bot.py:601–617`)
```python
reaction_queue = ReactionQueue()   # Creates thread-safe deque, starts nothing
storage = None                     # Lazy init
bot = commands.Bot(...)            # Creates Discord client
```
- The `bot` client is created at import time, which means any test that `import chatd.bot` will initialize the Discord intent mask from the config singleton. Tests must carefully mock `config` before importing.
- `reaction_queue` being a module-level singleton means tests share state unless explicitly reset.
- Recommendation: Wrap these in a `create_bot()` factory function. Effort: 1–2 hours.

**Phase 17 TODO** (`chatd/bot.py:807`)
```python
# TODO: Process updated roles for Discord message updates (Phase 17)
```
- Job updates are detected and logged but not acted on. This is a known gap.
- Recommendation: Track in an issue/ticket rather than a code comment.

#### 🟢 Low Priority

- Emoji usage in log messages (🚀, ✅, 💥) is charming but can cause issues in log parsers and grep. Worth making consistent — currently used in ~40% of log statements, not all.
- The `check_for_new_roles` function at ~107 lines does: git pull check, change detection, message posting, and reaction queuing. Could be broken into 3–4 smaller functions for clarity.

---

## Metrics

| Metric | Value |
|---|---|
| Files analyzed | 19 Python source files |
| Lines of code (source) | 5,072 |
| Lines of code (tests) | 12,202 |
| Test-to-code ratio | 2.4x |
| Broad `except Exception` catches | 69 |
| Bare `except:` | 1 (`messages.py:62`) |
| Duplicated `detect_job_changes` | 3 copies |
| Module-level globals | 5 (`reaction_queue`, `storage`, `bot`, `failed_channels`, `channel_failure_counts`) |
| TODO comments | 1 (Phase 17) |
| Hardcoded secrets | 0 |
| Subprocess calls | 2 (safe, explicit arg lists) |
| Database connection resilience | Missing `pool_pre_ping` |

---

## Prioritized Action Plan

### Quick Wins (< 1 day)

1. **Add `pool_pre_ping=True, pool_recycle=3600`** to `create_engine` in `database.py:159` — prevents silent connection drops
2. **Fix bare `except:`** in `messages.py:62` → `except Exception:`
3. **Add `exc_info=True`** to ~15 `logger.error(f"...: {e}")` calls in `bot.py` for full tracebacks
4. **Change `logger.info` → `logger.debug`** at `storage_abstraction.py:1024`
5. **Fix `tuple[bool, bool]`** → `Tuple[bool, bool]` in `storage_abstraction.py:387`
6. **Fix TOCTOU** in SIGHUP handler in `logging_utils.py`

### Medium-Term (1–5 days)

7. **Deduplicate `detect_job_changes`** — extract shared logic to a free function (~1 hour)
8. **Replace `schedule` + `bot.loop`** with `discord.ext.tasks.loop` — more idiomatic and removes deprecated API (~2 hours)
9. **Remove `storage.py`** and update `test_integration.py:399` — reduce dead code (~30 min)
10. **Add `pool_recycle`** and test connection resilience after 8h idle
11. **Add `pytest-cov`** and measure actual coverage baseline
12. **Add channel unblocking mechanism** — currently `failed_channels` only clears on restart

### Long-Term (> 5 days)

13. **Split `bot.py`** into `reaction_queue.py`, `event_handlers.py`, `dm_handlers.py`, `scheduler.py`
14. **Split `storage_abstraction.py`** into `json_backend.py` + `database_backend.py` + `data_storage.py`
15. **Refactor module-level globals in `bot.py`** into a `create_bot()` factory for better testability
16. **Implement Phase 17** (Discord message updates for modified jobs) — already partially scaffolded
