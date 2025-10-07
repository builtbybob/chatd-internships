# Copilot Instructions for chatd-internships Project

## Virtual Environment Requirement
**CRITICAL:** Always use the Python virtual environment when running Python commands, tests, or scripts in this project. The virtual environment is located at `.venv/` and must be activated before any Python operations.

When running Python commands in the terminal, ensure you use:
- `source .venv/bin/activate` first, or
- Use the full path: `/opt/chatd/.venv/bin/python` for Python commands
- Use the full path: `/opt/chatd/.venv/bin/pytest` for pytest commands

## Test Environment
- Test framework: pytest
- Total tests: ~125 tests across multiple test files
- Run tests with: `python -m pytest tests/ -v` (after activating venv)
- Common test patterns: Mock configurations may need `message_post_delay` and `max_retries` properties

## Project Structure
- Main application: `main.py`
- Core modules in `chatd/` directory
- Configuration management via `chatd/config.py`
- Database operations via `chatd/database.py`
- Discord bot functionality in `chatd/bot.py`
- Storage abstraction for JSON/database dual support

## Development Workflow
1. Always activate virtual environment first
2. Run tests before and after code changes
3. Use semantic_search for codebase exploration
4. Mock external dependencies (Discord API, file system, database) in tests
5. Maintain backwards compatibility with existing data formats