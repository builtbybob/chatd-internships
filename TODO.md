# ChatD Internships Bot - TODO & Future Improvements

This document tracks planned improvements and enhancements for the ChatD Internships Discord bot.

## 🚀 Priority Items

### 1. Dynamic Log Level Control
**Goal**: Update logging levels on the fly without process restart

**Current Issue**: Changing log levels requires systemctl restart, causing service interruption

**Implementation Plan**:
- [ ] **1.1** Enhance signal handlers in `logging_utils.py`
  - [ ] Currently supports SIGUSR1/SIGUSR2 for level changes
  - [ ] Add Docker-compatible signal sending via `docker exec`
  - [ ] Test: `docker exec chatd-bot python -c "import os, signal; os.kill(1, signal.SIGUSR1)"`
- [ ] **1.2** Add management command support
  - [ ] Extend `chatd` script with `chatd loglevel debug|info|warning|error`
  - [ ] Implementation: `sudo docker exec chatd-bot python -c "import signal, os; os.kill(1, signal.SIGUSR1)"`
- [ ] **1.3** Add REST API endpoint (optional)
  - [ ] Simple HTTP server for log level changes
  - [ ] Secure with basic auth or token
- [ ] **1.4** Document runtime log level control in README

**Files to modify**: `chatd/logging_utils.py`, `scripts/chatd`, `README.md`

### 2. Optimize Docker Build Performance
**Goal**: Separate build and run phases to eliminate slow startup times

**Current Issue**: `systemctl start` rebuilds Docker image every time (~30-60 seconds)

**Implementation Plan**:
- [ ] **2.1** Modify systemd service strategy
  - [ ] Remove `ExecStartPre` Docker build step
  - [ ] Create separate build workflow
- [ ] **2.2** Add build management commands
  - [ ] `chatd-build`: Manual rebuild trigger
  - [ ] `chatd-deploy`: Build + restart in one command
- [ ] **2.3** Implement image versioning
  - [ ] Tag images with git commit hash: `chatd-internships:${GIT_COMMIT}`
  - [ ] Track current deployment version
- [ ] **2.4** Add CI/CD build hooks
  - [ ] GitHub Actions to build and push images
  - [ ] Local deployment pulls pre-built images
- [ ] **2.5** Update systemd service file
  - [ ] Remove build steps from service startup
  - [ ] Add health checks for faster failure detection

**Files to modify**: `chatd-internships.service`, `scripts/chatd-build`, `Dockerfile`

### 3. Asynchronous Message Reactions
**Goal**: Improve reaction performance through async processing

**Current Issue**: Adding reactions blocks message sending, slowing overall performance

**Implementation Plan**:
- [ ] **3.1** Refactor reaction logic in `bot.py`
  - [ ] Move reactions to background task queue
  - [ ] Use `asyncio.create_task()` for non-blocking reactions
- [ ] **3.2** Implement reaction batching
  - [ ] Queue reactions and process in batches
  - [ ] Add configurable delay between reaction batches
- [ ] **3.3** Add reaction failure handling
  - [ ] Retry logic for failed reactions
  - [ ] Graceful degradation when reactions fail
- [ ] **3.4** Configuration options
  - [ ] `REACTION_BATCH_SIZE=10`
  - [ ] `REACTION_DELAY_MS=100`
  - [ ] `REACTION_RETRY_COUNT=3`

**Files to modify**: `chatd/bot.py`, `chatd/config.py`

## 🎯 Feature Enhancements

### 4. Smart Reaction-Based Info Sharing
**Goal**: Enhanced info messages triggered by specific reactions

**Current Behavior**: All reactions trigger DM with job details
**Target Behavior**: Only '❓' reaction triggers enhanced company info

**Implementation Plan**:
- [ ] **4.1** Update reaction handler logic
  - [ ] Check reaction emoji type before processing
  - [ ] Only process '❓' emoji for detailed info
- [ ] **4.2** Enhanced company information gathering
  - [ ] Query `listings.json` for same company roles
  - [ ] Filter by configurable time window (default: 7 days)
  - [ ] Group by company and format nicely
- [ ] **4.3** Rich DM formatting
  - [ ] Company overview section
  - [ ] All recent roles from company
  - [ ] Application deadlines and dates
  - [ ] Direct links to applications
- [ ] **4.4** Configuration options
  - [ ] `COMPANY_INFO_DAYS=7`
  - [ ] `INFO_REACTION_EMOJI=❓`
  - [ ] `ENABLE_COMPANY_INFO=true`

**Files to modify**: `chatd/bot.py`, `chatd/messages.py`, `chatd/config.py`

### 5. Configurable Date Filtering
**Goal**: Make "too old" threshold configurable instead of hardcoded

**Current Implementation**: Hardcoded 5-day filter in code
**Target**: Environment variable configuration

**Implementation Plan**:
- [ ] **5.1** Add configuration variable
  - [ ] `MAX_POST_AGE_DAYS=5` in `.env`
  - [ ] Update `config.py` to load this setting
- [ ] **5.2** Update filtering logic
  - [ ] Replace hardcoded values in message processing
  - [ ] Apply consistently across all date checks
- [ ] **5.3** Add validation
  - [ ] Ensure positive integer values
  - [ ] Reasonable bounds (1-30 days)
- [ ] **5.4** Document in README
  - [ ] Explain impact of different values
  - [ ] Recommended settings

**Files to modify**: `chatd/config.py`, `chatd/bot.py`, `.env.example`, `README.md`

## 🔍 Data Quality & Performance

### 6. Listings Data Audit
**Goal**: Comprehensive audit of matching logic accuracy

**Scope**: Ensure no false positives or missed matches in role detection

**Status**: **PARTIALLY COMPLETED** - Critical matching logic improved

**Implementation Plan**:
- [x] **6.2** Key matching validation **COMPLETED**
  - [x] Enhanced `normalize_role_key()` to include `date_posted`
  - [x] Fixed over-matching that prevented re-opening detection
  - [x] Updated unit tests with comprehensive edge case coverage
  - [x] Added specific test for re-opening scenario validation
- [ ] **6.1** Create audit tooling
  - [ ] Script to analyze `listings.json` structure
  - [ ] Compare against known test data
  - [ ] Generate matching statistics report
- [ ] **6.3** Historical data analysis
  - [ ] Process last 30 days of changes
  - [ ] Identify any missed or duplicate postings
  - [ ] Compare against Discord message history
- [ ] **6.4** Unit test expansion
  - [x] Enhanced existing matching test cases
  - [ ] Edge case coverage (special characters, unicode, etc.)
  - [ ] Performance benchmarks for large datasets
- [ ] **6.5** Documentation
  - [ ] Document matching algorithm details
  - [ ] Create troubleshooting guide for edge cases

**Key Improvement Made**:
```python
# OLD: Over-matching (missed re-openings)
"company__title"

# NEW: Precise matching (detects re-openings)  
"company__title__date_posted"
```

**Files to create**: `scripts/audit_listings.py`, `tests/test_matching_audit.py`
**Files to modify**: `tests/test_messages.py`, `chatd/messages.py`

### 7. Efficient Delta Processing
**Goal**: Process only changes instead of full file comparison

**Current Approach**: Full file read and comparison on every check
**Target**: Git diff-based change detection

**Implementation Plan**:
- [ ] **7.1** Git diff integration
  - [ ] Use `git diff HEAD~1 HEAD -- .github/scripts/listings.json`
  - [ ] Parse diff output to identify changed entries
  - [ ] Only process modified/added/removed entries
- [ ] **7.2** Change type detection
  - [ ] Identify additions, modifications, deletions
  - [ ] Handle role status changes (active -> inactive)
  - [ ] Track position changes within file
- [ ] **7.3** Incremental processing
  - [ ] Cache current state more efficiently
  - [ ] Only update Discord for actual changes
  - [ ] Reduce memory usage for large datasets
- [ ] **7.4** Performance monitoring
  - [ ] Add timing metrics for processing phases
  - [ ] Monitor memory usage improvements
  - [ ] Log statistics about change volumes
- [ ] **7.5** Fallback mechanism
  - [ ] Full processing mode for edge cases
  - [ ] Recovery from delta processing errors

**Files to modify**: `chatd/repo.py`, `chatd/storage.py`, `chatd/bot.py`

### 8. Role Status Management
**Goal**: Handle role deactivations and visibility changes

**Current Behavior**: Only posts new roles, ignores status changes
**Target**: Update/modify past messages when roles change status

**Implementation Plan**:
- [ ] **8.1** Message tracking enhancement
  - [ ] Store Discord message IDs with role keys
  - [ ] Track message-to-role mapping in storage
  - [ ] Add message update capabilities
- [ ] **8.2** Status change detection
  - [ ] Compare `visible` and `active` flags between updates
  - [ ] Identify roles that changed from active to inactive
  - [ ] Track roles that became hidden/invisible
- [ ] **8.3** Message modification strategies
  - [ ] **Option A**: Edit original message with strikethrough text
  - [ ] **Option B**: Add reaction (❌) to indicate closure
  - [ ] **Option C**: Reply with update status
  - [ ] **Option D**: Delete message entirely
- [ ] **8.4** Configuration options
  - [ ] `HANDLE_DEACTIVATIONS=true`
  - [ ] `DEACTIVATION_STRATEGY=edit|react|reply|delete`
  - [ ] `DEACTIVATION_MESSAGE="🚫 This position is no longer available"`
- [ ] **8.5** Bulk status processing
  - [ ] Handle multiple simultaneous status changes
  - [ ] Rate limit message updates to avoid API limits
  - [ ] Error handling for messages that can't be modified

**Files to modify**: `chatd/storage.py`, `chatd/bot.py`, `chatd/messages.py`, `chatd/config.py`

## 📋 Implementation Notes

### Development Workflow
1. **Create feature branches** for each TODO item
2. **Add unit tests** before implementing features
3. **Update configuration documentation** for any new settings
4. **Test in development environment** before production deployment
5. **Update README.md** with new features and configuration options

### Configuration Management
- All new settings should have sensible defaults
- Add validation for configuration values
- Document impact and recommended values
- Consider backward compatibility

### Testing Strategy
- **Unit tests**: Individual component testing
- **Integration tests**: Full workflow testing
- **Performance tests**: Benchmark improvements
- **Production validation**: Test with real data in controlled manner

### Deployment Considerations
- **Zero-downtime deployment** for non-breaking changes
- **Database migration strategy** for storage changes
- **Rollback procedures** for failed deployments
- **Monitoring and alerting** for new features

---

## ✅ Completed Improvements

### **Role Matching Logic Enhancement** *(September 21, 2025)*
**Problem**: Over-matching prevented detection of role re-openings
- Same company posting identical role titles resulted in missed notifications
- Bot couldn't distinguish between original posting and re-openings

**Solution**: Enhanced `normalize_role_key()` function
```python
# Before: company__title
# After:  company__title__date_posted
```

**Impact**: 
- [x] Role re-openings now properly detected and posted
- [x] Prevents duplicate notifications for minor data updates  
- [x] Maintains stable keys for legitimate role updates
- [x] Added comprehensive test coverage including re-opening scenarios

**Files Modified**: `chatd/repo.py`, `tests/test_repo.py`

---

## 📊 Progress Tracking

- [x] **Critical Fixes**: 1/1 (Role matching logic)
- [ ] **Items Started**: 1/8 (Data audit partially completed)
- [ ] **Items Completed**: 0/8 (Full feature completion)
- [ ] **Total Sub-tasks**: 4/35 completed

*Last Updated: September 21, 2025*
