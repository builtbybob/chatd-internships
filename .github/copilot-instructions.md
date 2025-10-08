# Copilot Instructions for chatd-internships Project

## Behavior
- Provide clear, concise, and accurate code suggestions.
- Follow best practices for Python, Docker, and related technologies.
- Be objective and neutral in tone, avoid unnecessary compliments.
- Prioritize security, efficiency, and maintainability in code suggestions.

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

## Git Workflow and Branch Protection
**CRITICAL:** Always verify you're on the correct branch before committing and pushing changes.

### Branch Protection Standards
- **Never push directly to `main`** - use feature branches and pull requests
- **Always check current branch** with `git branch` or `git status` before committing
- **Create feature branches** for all changes: `git checkout -b feature/description`
- **Push feature branches** first: `git push origin feature/branch-name`
- **Create pull requests** to merge into main via GitHub web interface

### Required Git Commands Before Any Commit
```bash
# 1. Always check current branch first
git branch
# or
git status

# 2. If on main, create and switch to feature branch
git checkout -b feature/your-feature-name

# 3. After committing, push to feature branch (not main)
git push origin feature/your-feature-name

# 4. Create pull request via GitHub web interface
```

### Branch Naming Convention
- `feature/description` - for new features
- `bugfix/description` - for bug fixes  
- `docs/description` - for documentation updates
- `refactor/description` - for code refactoring

**Remember**: Main branch should only receive changes via reviewed pull requests.