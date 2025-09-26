# ChatD Internships Bot - TODO & Future Improvements

This document tracks planned improvements and enhancements for the ChatD Internships Discord bot.

## 🚀 Priority Items

### 1. Dynamic Log Level Control ✅ **COMPLETED**
**Goal**: Update logging levels on the fly without process restart

**Current Issue**: ~~Changing log levels requires systemctl restart, causing service interruption~~ **RESOLVED**

**Implementation Plan**:
- [x] **1.1** Enhance signal handlers in `logging_utils.py`
  - [x] Added SIGHUP signal handler for direct level changes
  - [x] Docker-compatible signal sending via `docker kill --signal=HUP`
  - [x] File-based level communication system for clean Docker integration
- [x] **1.2** Add management command support
  - [x] Added `chatd-loglevel` command with full level support
  - [x] Supports all levels: `debug|info|warning|error|critical`
  - [x] Clean, intuitive command interface with helpful error messages
- [x] **1.3** Simplified implementation
  - [x] Removed complex incremental up/down signal handlers
  - [x] Single, clear approach for direct level setting
  - [x] Professional command-line interface matching standard tools
- [x] **1.4** Document runtime log level control
  - [x] Added comprehensive usage documentation
  - [x] Updated management scripts help text

**Results Achieved**:
- **Instant log level changes**: Change from INFO to DEBUG without any service interruption
- **Professional interface**: `sudo chatd-loglevel debug` provides immediate verbose logging
- **Production-ready**: Enables instant troubleshooting of live issues
- **Clean implementation**: Single signal handler approach, no complexity
- **Full level support**: All 5 standard log levels (debug/info/warning/error/critical)

**Files modified**: `chatd/logging_utils.py`, `scripts/create-management-scripts.sh`

### 2. Optimize Docker Build Performance ✅ **COMPLETED**
**Goal**: Separate build and run phases to eliminate slow startup times

**Current Issue**: ~~`systemctl start` rebuilds Docker image every time (~30-60 seconds)~~ **RESOLVED**

**Implementation Plan**:
- [x] **2.1** Modify systemd service strategy
  - [x] Remove `ExecStartPre` Docker build step
  - [x] Create separate build workflow
- [x] **2.2** Add build management commands
  - [x] `chatd build`: Manual rebuild trigger
  - [x] `chatd deploy`: Deploy with existing image
  - [x] `chatd update`: Build + restart in one command
- [x] **2.3** Implement image versioning
  - [x] Tag images with git commit hash: `chatd-internships:${GIT_COMMIT}`
  - [x] Track current deployment version
- [x] **2.4** Enhanced management tooling
  - [x] User-agnostic build process with CHATD_BRANCH environment variable
  - [x] Enhanced management scripts with better error handling
  - [x] Build verification and deployment validation
- [x] **2.5** Update systemd service file
  - [x] Remove build steps from service startup
  - [x] Add health checks for faster failure detection

**Results Achieved**:
- **Deployment time**: Reduced from ~4+ minutes to ~8 seconds
- **Build separation**: Can now build once, deploy multiple times
- **Smart builds**: Skip rebuilds when no code changes (~0.5 seconds)
- **Version tracking**: Git commit-based image tagging and management
- **New commands**: `chatd build`, `chatd deploy`, `chatd update`, `chatd version`
- **Faster iteration**: Quick deployments for testing and rollbacks
- **Enhanced tooling**: User-agnostic build process with CHATD_BRANCH support

**Files modified**: `chatd-internships.service`, `scripts/create-management-scripts.sh`

### 3. Docker Image Auto-Pruning 🧹 **(Quick Win - High Priority)**
**Goal**: Automatically clean up old Docker images to prevent disk space issues

**Current Issue**: Multiple Docker images accumulate (386MB each), consuming limited disk space
**Current State**: 3 images = ~1.1GB, only 505MB free space remaining

**Implementation Plan**: ✅ **COMPLETED**
- [x] **3.1** Add auto-pruning to deployment workflow
  - [x] Modify `chatd-update` script to retain only N latest versions (default: 3)
  - [x] Keep current commit and 2 previous versions (N-1 and N-2 rollback capability)
  - [x] Automatic cleanup after successful deployment
  - [x] Configuration option for retention count: `DOCKER_IMAGE_RETENTION=3`
- [x] **3.2** Manual cleanup commands
  - [x] Add `chatd cleanup` command for manual image pruning
  - [x] Add `chatd images` command to list current images with sizes
  - [x] Add `chatd prune` command for aggressive cleanup (keep only latest)
  - [x] Dry-run mode: `chatd cleanup --dry-run` to preview what would be deleted
- [x] **3.3** Disk space monitoring integration
  - [x] Check available disk space before building new images
  - [x] Automatic emergency cleanup if disk usage > 90%
  - [x] Warning messages when approaching space limits
  - [x] Integration with future monitoring dashboard alerts

**Example Auto-Pruning Logic**:
```bash
# In chatd-update script, after successful deployment:
echo "🧹 Cleaning up old Docker images..."
RETENTION_COUNT=${DOCKER_IMAGE_RETENTION:-3}

echo "📊 Retention policy: keeping $RETENTION_COUNT images (current + 2 rollback options)"

# Get all chatd images sorted by creation date (newest first)
IMAGES=$(docker images chatd-internships --format "{{.Tag}}" | head -n +$RETENTION_COUNT)

# Remove images older than retention count
docker images chatd-internships --format "{{.Tag}}" | tail -n +$((RETENTION_COUNT + 1)) | while read tag; do
    if [[ "$tag" != "latest" ]]; then
        echo "🗑️  Removing old image: chatd-internships:$tag"
        docker rmi "chatd-internships:$tag" 2>/dev/null || true
    fi
done

echo "✅ Cleanup complete. Retained $RETENTION_COUNT images."
```

**New Management Commands**:
```bash
# Image management
sudo chatd images                    # List all ChatD images with sizes
sudo chatd cleanup                   # Clean up old images (keep 3)
sudo chatd cleanup --count 5         # Keep 5 images instead of 3
sudo chatd cleanup --dry-run         # Preview what would be deleted
sudo chatd prune                     # Aggressive cleanup (keep only latest)

# Disk space monitoring
sudo chatd disk                      # Show disk usage and image sizes
sudo chatd disk --alert              # Check if cleanup needed
```

**Disk Space Recovery**:
- **Current**: 3 images × 386MB = ~1.1GB used
- **After cleanup**: 3 images × 386MB = ~1.1GB (prevents growth beyond 3 images)
- **Emergency cleanup**: 1 image × 386MB = ~770MB total recovered

**Time to Implement**: ~30-45 minutes (high impact, low effort)

**Files to modify**:
- `scripts/create-management-scripts.sh` (add new cleanup commands)

**Results Achieved**:
- **Prevent disk space exhaustion** with current 7GB constraint
- **Automatic maintenance** - no manual intervention needed
- **Configurable retention** - balance between rollback capability and space
- **Emergency cleanup** - automatic recovery from space issues
- **Better visibility** - commands to monitor image usage

### 4. Asynchronous Message Reactions
**Goal**: Improve reaction performance through async processing

**Current Issue**: Adding reactions blocks message sending, slowing overall performance

**Implementation Plan**:
- [ ] **4.1** Refactor reaction logic in `bot.py`
  - [ ] Move reactions to background task queue
  - [ ] Use `asyncio.create_task()` for non-blocking reactions
- [ ] **4.2** Implement reaction batching
  - [ ] Queue reactions and process in batches
  - [ ] Add configurable delay between reaction batches
- [ ] **4.3** Add reaction failure handling
  - [ ] Retry logic for failed reactions
  - [ ] Graceful degradation when reactions fail
- [ ] **4.4** Configuration options
  - [ ] `REACTION_BATCH_SIZE=10`
  - [ ] `REACTION_DELAY_MS=100`
  - [ ] `REACTION_RETRY_COUNT=3`

**Files to modify**: `chatd/bot.py`, `chatd/config.py`

## 🎯 Feature Enhancements

### 5. Smart Reaction-Based Info Sharing
**Goal**: Enhanced info messages triggered by specific reactions

**Current Behavior**: All reactions trigger DM with job details
**Target Behavior**: Only '❓' reaction triggers enhanced company info

**Implementation Plan**:
- [ ] **5.1** Update reaction handler logic
  - [ ] Check reaction emoji type before processing
  - [ ] Only process '❓' emoji for detailed info
- [ ] **5.2** Enhanced company information gathering
  - [ ] Query `listings.json` for same company roles
  - [ ] Filter by configurable time window (default: 7 days)
  - [ ] Group by company and format nicely
- [ ] **5.3** Rich DM formatting
  - [ ] Company overview section
  - [ ] All recent roles from company
  - [ ] Application deadlines and dates
  - [ ] Direct links to applications
- [ ] **5.4** Configuration options
  - [ ] `COMPANY_INFO_DAYS=7`
  - [ ] `INFO_REACTION_EMOJI=❓`
  - [ ] `ENABLE_COMPANY_INFO=true`

**Files to modify**: `chatd/bot.py`, `chatd/messages.py`, `chatd/config.py`

### 6. Configurable Date Filtering ✅ **COMPLETED**
**Goal**: Make "too old" threshold configurable instead of hardcoded

**Current Implementation**: ~~Hardcoded 5-day filter in code~~ **RESOLVED**
**Target**: Environment variable configuration ✅ **ACHIEVED**

**Implementation Plan**:
- [x] **5.1** Add configuration variable ✅ **COMPLETED**
  - [x] `MAX_POST_AGE_DAYS=5` in `.env`
  - [x] Update `config.py` to load this setting
- [x] **5.2** Update filtering logic ✅ **COMPLETED**
  - [x] Replace hardcoded values in message processing
  - [x] Apply consistently across all date checks
- [x] **5.3** Add validation ✅ **COMPLETED**
  - [x] Ensure positive integer values
  - [x] Reasonable bounds (1-30 days)
- [x] **5.4** Document in README ✅ **COMPLETED**
  - [x] Explain impact of different values
  - [x] Added to .env.example

**Results Achieved**:
- **Configurable filtering**: MAX_POST_AGE_DAYS environment variable
- **Backward compatible**: Defaults to 5 days (existing behavior)
- **Validation**: 1-30 day range with helpful error messages
- **Flexible operations**: Can adjust based on deployment needs
- **Enhanced logging**: Shows configured max age in debug output

**Files modified**: `chatd/config.py`, `chatd/bot.py`, `.env.example`

## 🔍 Data Quality & Performance

### 7. Listings Data Audit
**Goal**: Comprehensive audit of matching logic accuracy

**Scope**: Ensure no false positives or missed matches in role detection

**Status**: **COMPLETED** ✅ - ID-based tracking implementation eliminates matching complexity

**Implementation Results**:
- [x] **7.1** Critical architectural improvement ✅ **COMPLETED**
  - [x] Migrated from composite key matching to direct UUID-based tracking
  - [x] Eliminated complex `get_role_id()` and `normalize_role_key()` functions
  - [x] Now uses direct `role['id']` access from listings.json (100% unique coverage)
  - [x] Production data migration completed (319/325 messages migrated successfully)
- [x] **7.2** Enhanced system reliability ✅ **COMPLETED**  
  - [x] Removed over-matching issues that prevented re-opening detection
  - [x] Simplified codebase from complex matching logic to straightforward ID lookups
  - [x] Validated 9,747 unique IDs in listings.json with 100% uniqueness
  - [x] Updated unit tests and removed obsolete matching test cases
- [x] **7.3** Production deployment ✅ **COMPLETED**
  - [x] Successful migration script execution with comprehensive backup
  - [x] Enhanced management scripts with user-agnostic build process
  - [x] Docker build verification and deployment to production
  - [x] Bot now operational with new ID-based architecture

**Key Improvement Made**:
```python
# OLD: Complex matching with potential issues
def get_role_id(role_data):
    # 28-line function with normalization and composite keys
    return f"{company}__{title}__{date_posted}"

# NEW: Direct UUID access (bulletproof)
role_id = role['id']  # Direct access to unique UUID from listings.json
```

**Results Achieved**:
- **100% reliable tracking**: Direct UUID access eliminates matching ambiguity
- **Simplified maintenance**: Removed 50+ lines of complex matching code
- **Production ready**: Successfully deployed with migrated data
- **Future-proof**: ID-based system scales with listings.json growth

**Files modified**: `chatd/repo.py`, `chatd/bot.py`, `scripts/migrate-to-id-keys.py`

### 8. Efficient Delta Processing
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

### 9. Role Status Management
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

### 10. Enhanced Monitoring & Observability
**Goal**: Better visibility into bot performance and health

**Benefits**: Proactive issue detection, performance optimization insights, operational visibility

**Implementation Plan**:
- [ ] **9.1** Add metrics collection
  - [ ] Track messages processed per minute
  - [ ] Monitor Discord API rate limits and usage
  - [ ] Count successful vs failed operations
  - [ ] Memory and CPU usage tracking
- [ ] **9.2** Health check endpoint
  - [ ] Simple HTTP server for container health checks
  - [ ] Validate Discord connection status
  - [ ] Check git repository accessibility
  - [ ] Verify data directory write permissions
- [ ] **9.3** Alert system
  - [ ] Discord webhook for bot errors/failures
  - [ ] Email notifications for critical issues
  - [ ] Rate limit warnings
  - [ ] Repository sync failure alerts
- [ ] **9.4** Performance dashboards
  - [ ] Log parsing and visualization
  - [ ] Historical trend analysis
  - [ ] Repository processing time metrics
  - [ ] Error rate tracking

**Files to modify**: `chatd/bot.py`, `chatd/config.py`, `main.py`, `requirements.txt`

### 11. Configuration Validation & Safety ✅ **COMPLETED**
**Goal**: Prevent misconfigurations and provide better error messages

**Benefits**: Faster debugging, prevents runtime failures, improves user experience

**Implementation Plan**:
- [x] **10.1** Startup validation ✅ **COMPLETED**
  - [x] Verify Discord token format and validity before starting
  - [x] Test channel access permissions and format validation
  - [x] Validate repository URL accessibility
  - [x] Check required environment variables
  - [x] Validate file system permissions for data directories
- [x] **10.2** Enhanced error reporting ✅ **COMPLETED**
  - [x] User-friendly error messages with emoji indicators
  - [x] Actionable troubleshooting advice in error messages
  - [x] Clear validation progress reporting
  - [x] Graceful startup failure with helpful guidance
- [x] **10.3** Comprehensive validation checks ✅ **COMPLETED**
  - [x] Discord token format validation (length and structure)
  - [x] Channel ID format and Discord snowflake validation
  - [x] Numeric configuration range validation (intervals, retries, etc.)
  - [x] Git command availability and repository access testing
  - [x] Directory write permission validation

**Results Achieved**:
- **Early error detection**: Configuration issues caught before bot startup
- **Better debugging**: Clear, actionable error messages with specific solutions
- **Professional validation**: Comprehensive checks for all critical components
- **User-friendly feedback**: Emoji-enhanced progress reporting and error descriptions
- **Robust startup**: Bot only starts if all validations pass

**Example validation output**:
```
🔍 Starting configuration validation...
✅ Discord token format validation passed
✅ Channel IDs validation passed (2 channels configured)
✅ Numeric configuration validation passed
✅ File permissions validation passed
✅ Repository accessibility validation passed
🔍 Testing Discord connection...
✅ Discord connection successful (logged in as ChatD Bot#1234)
✅ Can access 2/2 configured channels
✅ Configuration validation passed.
```

**Files modified**: `chatd/config.py`, `main.py`

### 12. Backup & Recovery System 🎯 **(Stretch Goal)**
**Goal**: Automated backup and disaster recovery procedures

**Note**: Limited by device storage constraints - requires external storage solution

**Implementation Plan**:
- [ ] **11.1** Lightweight backup strategy
  - [ ] Configuration and critical data backup only
  - [ ] Compressed backup to external storage/cloud
  - [ ] Exclude logs and temporary files
- [ ] **11.2** Recovery procedures
  - [ ] One-command restore from backup
  - [ ] Database corruption recovery
  - [ ] Configuration restoration
- [ ] **11.3** External storage integration
  - [ ] Cloud storage backup (S3, Google Drive, etc.)
  - [ ] Remote server backup via SSH
  - [ ] USB/external drive backup support
- [ ] **11.4** Backup validation
  - [ ] Backup integrity checks
  - [ ] Minimal test restore procedures
  - [ ] Backup retention policies

**Files to modify**: `scripts/chatd-backup`, `chatd/config.py`, `scripts/recovery.sh`

### 13. Multi-Environment Support 🎯 **(Requires Larger Disk)**
**Goal**: Support for development, staging, and production environments

**Benefits**: Safe testing, isolated development, professional deployment workflow, separate Discord bots for testing

**Prerequisites**: 
- **Larger microSD card** (current 7GB insufficient for multiple environments)
- **Separate Discord bot** for development environment
- **Environment isolation** to prevent dev changes affecting production

**Implementation Plan**:
- [ ] **12.1** Environment configuration structure
  - [ ] Separate Discord bots and tokens for dev/prod environments
  - [ ] Environment-specific Discord channels for testing
  - [ ] Environment-specific repository branches (dev/staging/main)
  - [ ] Isolated data storage per environment (`/var/lib/chatd-dev/`, `/var/lib/chatd-prod/`)
  - [ ] Environment-aware logging and monitoring
- [ ] **12.2** Configuration management
  - [ ] `.env.dev`, `.env.staging`, `.env.prod` configuration files
  - [ ] Environment inheritance (dev inherits from base, overrides specific values)
  - [ ] Separate Discord bot tokens and channel IDs per environment
  - [ ] Environment-specific repository URLs or branches
  - [ ] Configurable data directories and log files per environment
- [ ] **12.3** Development workflow improvements
  - [ ] Local development with test data and separate Discord bot
  - [ ] Development environment for testing changes safely
  - [ ] Environment promotion procedures (dev → staging → prod)
  - [ ] Configuration validation per environment
  - [ ] Isolated Docker containers per environment
- [ ] **12.4** Deployment strategies
  - [ ] Environment-specific systemd services (`chatd-dev`, `chatd-prod`)
  - [ ] Blue-green deployment support for production
  - [ ] Environment-specific Docker images and tags
  - [ ] Automated environment provisioning scripts
  - [ ] Environment health checks and monitoring
- [ ] **12.5** Environment management tools
  - [ ] `chatd env list` - Show available environments and their status
  - [ ] `chatd env switch <env>` - Switch active environment for operations
  - [ ] `chatd env status <env>` - Show specific environment status
  - [ ] `chatd env deploy <env>` - Deploy to specific environment
  - [ ] `chatd env logs <env>` - View logs for specific environment
  - [ ] Environment-specific configuration validation
- [ ] **12.6** Testing and promotion workflow
  - [ ] Deploy changes to dev environment first
  - [ ] Automated testing in dev environment
  - [ ] Manual approval process for production deployment
  - [ ] Rollback procedures for failed deployments
  - [ ] Configuration drift detection between environments
- [ ] **12.7** Environment-aware test simulation
  - [ ] Migrate existing `setup_test_update.sh` to support multiple environments
  - [ ] Environment-specific test data simulation (dev/staging/prod)
  - [ ] Safe testing of message replay functionality per environment
  - [ ] Automated test scenario generation for development
  - [ ] Test data isolation to prevent cross-environment contamination

**Example Environment Structure**:
```
/etc/chatd/
├── .env.dev          # Development configuration
├── .env.staging      # Staging configuration  
├── .env.prod         # Production configuration
└── .env.base         # Shared base configuration

/var/lib/chatd/
├── dev/              # Development data
├── staging/          # Staging data
└── prod/             # Production data

Docker containers:
├── chatd-dev         # Development bot
├── chatd-staging     # Staging bot
└── chatd-prod        # Production bot
```

**Example Configuration Structure**:
```bash
# .env.base (shared settings)
REPO_URL=https://github.com/builtbybob/chatd-internships.git
MAX_POST_AGE_DAYS=5
CHECK_INTERVAL_MINUTES=1

# .env.dev (development overrides)
DISCORD_TOKEN=<dev_bot_token>
CHANNEL_IDS=<dev_channel_ids>
LOCAL_REPO_PATH=/app/dev/Summer2026-Internships
DATA_FILE=/var/lib/chatd/dev/previous_data.json
LOG_LEVEL=DEBUG
CHECK_INTERVAL_MINUTES=5

# .env.prod (production overrides)  
DISCORD_TOKEN=<prod_bot_token>
CHANNEL_IDS=<prod_channel_ids>
LOCAL_REPO_PATH=/app/prod/Summer2026-Internships
DATA_FILE=/var/lib/chatd/prod/previous_data.json
LOG_LEVEL=INFO
```

**Example Management Commands**:
```bash
# Environment management
sudo chatd env list                    # Show all environments
sudo chatd env status dev              # Check dev environment
sudo chatd env switch dev              # Set dev as active environment

# Environment-specific operations
sudo chatd-dev status                  # Dev environment status
sudo chatd-dev logs -f                 # Follow dev logs
sudo chatd-dev build                   # Build dev image
sudo chatd-dev deploy                  # Deploy to dev

sudo chatd-prod status                 # Production status
sudo chatd-prod deploy                 # Deploy to production
sudo chatd-prod rollback               # Rollback production

# Testing workflow
sudo chatd env deploy dev              # Deploy changes to dev first
sudo chatd env test dev                # Run tests in dev environment
sudo chatd env promote dev staging     # Promote dev to staging
sudo chatd env promote staging prod    # Promote staging to prod
```

**Disk Space Requirements**:
- **Current**: ~7GB total (90% full)
- **Multi-environment**: ~15-20GB recommended
  - Base system: ~2GB
  - Production environment: ~5GB  
  - Development environment: ~3GB
  - Staging environment: ~3GB
  - Docker images (multiple): ~3GB
  - Logs and backups: ~2GB
  - Buffer space: ~2GB

**Migration Dependencies**:
- ✅ **Migration scripts ready** (created in previous work)
- ⏳ **Larger microSD card** (waiting for physical access)
- ⏳ **Separate Discord bot creation** (requires Discord Developer Portal access)
- ⏳ **Additional disk space** (current 649MB free insufficient)

**Files to create**: 
- `.env.base`, `.env.dev`, `.env.staging`, `.env.prod`
- `scripts/setup-environments.sh`
- `scripts/environment-manager.sh` 
- `scripts/setup-test-update-multi-env.sh` (enhanced version of existing script)
- `chatd-internships-dev.service`, `chatd-internships-staging.service`

**Files to modify**: 
- `chatd/config.py` (environment detection and inheritance)
- `scripts/create-management-scripts.sh` (multi-environment commands)
- `chatd-internships.service` (production-specific service)
- `Dockerfile` (environment-aware builds)

### 14. Enhanced Test Simulation Framework 🧪 **(Depends on Multi-Environment)**
**Goal**: Migrate and enhance existing test simulation script for multi-environment support

**Current State**: `setup_test_update.sh` allows replaying message updates by resetting to older commits
**Target**: Environment-aware testing with isolated test data per environment

**Implementation Plan**:
- [ ] **13.1** Migrate existing test script to multi-environment
  - [ ] Create `setup-test-update-multi-env.sh` to replace current script
  - [ ] Environment parameter support: `./setup-test-update-multi-env.sh dev 3`
  - [ ] Support both commit count and specific commit hash: `./setup-test-update-multi-env.sh dev abc123f`
  - [ ] Automatic detection of commit hash vs number format
  - [ ] Environment-specific data paths and repository locations
  - [ ] Isolated test data per environment (no cross-contamination)
  - [ ] Environment-aware restoration procedures
- [ ] **13.2** Enhanced testing capabilities
  - [ ] Predefined test scenarios (small update, large batch, edge cases)
  - [ ] Test scenario library with known expected outcomes
  - [ ] Automated verification of bot responses to test data
  - [ ] Performance benchmarking during test runs
  - [ ] Test result logging and comparison
- [ ] **13.3** Development workflow integration
  - [ ] Quick test commands: `chatd test replay dev 5` (replay 5 commits in dev)
  - [ ] Integration with environment deployment workflow
  - [ ] Automated testing as part of promotion pipeline
  - [ ] Test data reset and cleanup procedures
  - [ ] Safe testing isolation (never affect production data)
- [ ] **13.4** Test data management
  - [ ] Environment-specific previous_data.json files
  - [ ] Test scenario snapshots and restoration points
  - [ ] Automated test data generation from real data
  - [ ] Test data anonymization for development
  - [ ] Version control for test scenarios

**Example Enhanced Usage**:
```bash
# Environment-specific testing with commit counts
./scripts/setup-test-update-multi-env.sh dev 3        # Test 3 commits back in dev
./scripts/setup-test-update-multi-env.sh staging 5    # Test 5 commits back in staging

# Environment-specific testing with specific commit hashes
./scripts/setup-test-update-multi-env.sh dev abc123f  # Test specific commit in dev
./scripts/setup-test-update-multi-env.sh staging 9f8e7d6c # Test specific commit in staging

# Quick test commands (after multi-env setup)
sudo chatd test replay dev 3                          # Replay test in dev environment
sudo chatd test replay dev abc123f                    # Replay specific commit in dev
sudo chatd test scenario dev batch-update             # Run predefined test scenario
sudo chatd test reset dev                             # Reset dev environment test data
sudo chatd test verify dev                            # Verify test results

# Safe production testing (read-only)
sudo chatd test simulate prod 2                       # Simulate without affecting prod data
sudo chatd test simulate prod abc123f                 # Simulate specific commit in read-only mode
```

**Example Script Structure**:
```bash
#!/bin/bash
# setup-test-update-multi-env.sh
# Enhanced test simulation with environment support

ENVIRONMENT=${1:-dev}    # Default to dev environment
COMMIT_REF=${2:-2}       # Default to 2 commits back, or accept specific commit hash

# Detect if COMMIT_REF is a commit hash or number
if [[ "$COMMIT_REF" =~ ^[a-f0-9]{6,40}$ ]]; then
    # It's a commit hash
    RESET_TARGET="$COMMIT_REF"
    echo "Using specific commit: $COMMIT_REF"
elif [[ "$COMMIT_REF" =~ ^[0-9]+$ ]]; then
    # It's a number of commits back
    RESET_TARGET="HEAD~$COMMIT_REF"
    echo "Going back $COMMIT_REF commits"
else
    echo "ERROR: Invalid commit reference. Use either a number (e.g., 3) or commit hash (e.g., abc123f)"
    exit 1
fi

# Environment-specific paths
case "$ENVIRONMENT" in
    dev)
        REPO_DIR="/app/dev/Summer2026-Internships"
        DATA_FILE="/var/lib/chatd/dev/previous_data.json"
        ;;
    staging)
        REPO_DIR="/app/staging/Summer2026-Internships"
        DATA_FILE="/var/lib/chatd/staging/previous_data.json"
        ;;
    prod)
        echo "ERROR: Direct production testing not allowed. Use simulate mode."
        exit 1
        ;;
    *)
        echo "ERROR: Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

# Validate environment is safe for testing
if [[ "$ENVIRONMENT" == "prod" ]]; then
    echo "Production environment testing requires special approval"
    exit 1
fi

# Reset to specified commit or commit count
echo "Resetting $ENVIRONMENT repository to: $RESET_TARGET"
cd "$REPO_DIR" || exit 1
git reset --hard "$RESET_TARGET"

# Environment-aware test setup...
```

**Integration with Multi-Environment**:
- **Development**: Full test replay capabilities with message posting
- **Staging**: Controlled testing with limited Discord channels  
- **Production**: Read-only simulation mode (no actual messages sent)
- **Isolation**: Each environment has separate test data and repositories

**Benefits**:
- **Safe development testing** with realistic data scenarios
- **Automated test verification** of bot behavior changes
- **Performance benchmarking** during feature development
- **Regression testing** to ensure changes don't break existing functionality
- **Environment isolation** prevents test data from affecting production

**Files to create**:
- `scripts/setup-test-update-multi-env.sh` (enhanced multi-environment version)
- `scripts/test-scenarios/` (directory for predefined test cases)
- `scripts/test-verification.sh` (automated test result verification)

**Files to modify**:
- `setup_test_update.sh` (mark as deprecated, reference new script)

### 15. Monitoring Dashboard & Alerting System 📊 **(High Priority)**
**Goal**: Comprehensive monitoring dashboard with real-time metrics, alerts, and historical analytics

**Benefits**: Proactive issue detection, performance insights, usage analytics, operational visibility

**Free Framework Options**:
- **Option A**: **Grafana + Prometheus + AlertManager** (Most popular, enterprise-grade)
- **Option B**: **InfluxDB + Telegraf + Grafana** (Time-series focused, great for metrics)
- **Option C**: **Elastic Stack (ELK)** (Elasticsearch + Logstash + Kibana - log-centric)
- **Option D**: **Zabbix** (All-in-one monitoring solution)

**Recommended Stack**: **Grafana + Prometheus + AlertManager** (industry standard, excellent Docker support)

**Implementation Plan**:
- [ ] **14.1** Metrics collection and export
  - [ ] Add Prometheus metrics endpoint to ChatD bot (`/metrics`)
  - [ ] Custom metrics for job postings, reactions, errors, response times
  - [ ] Discord API rate limit monitoring and usage tracking
  - [ ] System resource metrics (CPU, memory, disk, network)
  - [ ] Git repository sync metrics and timing
- [ ] **14.2** Prometheus setup and configuration
  - [ ] Prometheus server Docker container configuration
  - [ ] Metrics scraping configuration for ChatD bot
  - [ ] System metrics collection with node_exporter
  - [ ] Docker metrics collection with cadvisor
  - [ ] Retention policies and storage optimization
- [ ] **14.3** Grafana dashboard development
  - [ ] Real-time operations dashboard (job posts, errors, performance)
  - [ ] Historical analytics dashboard (trends, usage patterns)
  - [ ] System health dashboard (resources, uptime, alerts)
  - [ ] Business metrics dashboard (job posting statistics, engagement)
  - [ ] Alert status and incident management dashboard
- [ ] **14.4** AlertManager configuration
  - [ ] Error rate alerts (service failures, Discord API errors)
  - [ ] Performance alerts (slow response times, high memory usage)
  - [ ] Business logic alerts (no job posts for X hours, repo sync failures)
  - [ ] System alerts (disk space, high CPU, container restarts)
  - [ ] Alert routing and notification channels (Discord webhooks, email)
- [ ] **14.5** Integration and automation
  - [ ] Environment-specific monitoring (dev/staging/prod dashboards)
  - [ ] Automated dashboard provisioning and backup
  - [ ] Monitoring stack deployment automation
  - [ ] Integration with existing Docker and systemd infrastructure
  - [ ] Monitoring data backup and disaster recovery

**Key Metrics to Track**:
```yaml
# Business Metrics
- chatd_job_posts_total (counter)
- chatd_reactions_added_total (counter) 
- chatd_dm_messages_sent_total (counter)
- chatd_companies_processed_total (counter)
- chatd_duplicate_posts_filtered_total (counter)

# Performance Metrics  
- chatd_processing_duration_seconds (histogram)
- chatd_discord_api_requests_total (counter)
- chatd_discord_api_rate_limit_remaining (gauge)
- chatd_git_sync_duration_seconds (histogram)
- chatd_memory_usage_bytes (gauge)

# Error Metrics
- chatd_errors_total{type="discord_api|git_sync|processing"} (counter)
- chatd_failed_channels_total (counter)
- chatd_service_restarts_total (counter)

# System Metrics
- chatd_uptime_seconds (counter)
- chatd_last_successful_sync_timestamp (gauge)
- chatd_config_reload_total (counter)
```

**Dashboard Examples**:

**Real-time Operations Dashboard**:
- Live job posting rate (jobs/hour)
- Current processing status and queue length
- Discord API rate limit status
- Active errors and alerts
- Service uptime and health status

**Business Analytics Dashboard**:
- Daily/weekly job posting trends
- Top companies by job count
- Reaction engagement rates
- Popular job categories and locations
- Historical growth metrics

**System Health Dashboard**:
- CPU, memory, disk usage over time
- Container restart frequency
- Network I/O and Discord API performance
- Git repository sync health
- Log error rates and patterns

**Example Alert Rules**:
```yaml
# Service down alert
- alert: ChatDServiceDown
  expr: up{job="chatd"} == 0
  for: 1m
  annotations:
    summary: "ChatD service is down"
    description: "ChatD bot has been down for more than 1 minute"

# High error rate alert  
- alert: HighErrorRate
  expr: rate(chatd_errors_total[5m]) > 0.1
  for: 2m
  annotations:
    summary: "High error rate in ChatD"
    description: "Error rate is {{ $value }} errors/second"

# No job posts alert
- alert: NoJobPostsDetected
  expr: increase(chatd_job_posts_total[1h]) == 0
  for: 2h
  annotations:
    summary: "No job posts detected in 2 hours"
    description: "ChatD hasn't posted any jobs in the last 2 hours"

# High memory usage alert
- alert: HighMemoryUsage
  expr: chatd_memory_usage_bytes > 500 * 1024 * 1024  # 500MB
  for: 5m
  annotations:
    summary: "ChatD high memory usage"
    description: "Memory usage is {{ $value | humanize }}B"
```

**Docker Stack Configuration**:
```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: chatd-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    container_name: chatd-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=chatd_monitoring_2025

  alertmanager:
    image: prom/alertmanager:latest
    container_name: chatd-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml

volumes:
  prometheus_data:
  grafana_data:
```

**Integration with ChatD Bot**:
```python
# Add to chatd/bot.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Metrics
job_posts_total = Counter('chatd_job_posts_total', 'Total job posts sent')
reactions_total = Counter('chatd_reactions_added_total', 'Total reactions added')
processing_time = Histogram('chatd_processing_duration_seconds', 'Processing time')
discord_api_requests = Counter('chatd_discord_api_requests_total', 'Discord API requests')
errors_total = Counter('chatd_errors_total', 'Total errors', ['type'])

# Start metrics server
start_http_server(8000)  # Metrics available at http://localhost:8000/metrics
```

**Notification Channels**:
- **Discord webhooks** for immediate alerts
- **Email notifications** for critical issues
- **SMS alerts** for service down situations (via email-to-SMS)
- **Slack integration** if using team communication

**Disk Space Requirements**:
- **Monitoring stack**: ~2-3GB additional space
- **Metrics retention**: ~500MB per month (configurable)
- **Log storage**: ~1GB per month (configurable)
- **Total additional**: ~3-5GB for comprehensive monitoring

**Files to create**:
- `docker-compose.monitoring.yml` (monitoring stack)
- `monitoring/prometheus.yml` (Prometheus configuration)
- `monitoring/alertmanager.yml` (alert configuration)
- `monitoring/grafana/dashboards/` (dashboard definitions)
- `scripts/setup-monitoring.sh` (automated setup)
- `scripts/monitoring-backup.sh` (dashboard and config backup)

**Files to modify**:
- `chatd/bot.py` (add Prometheus metrics)
- `chatd/config.py` (monitoring configuration options)
- `requirements.txt` (add prometheus_client)
- `Dockerfile` (expose metrics port)
- `README.md` (monitoring setup documentation)

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

### **Dynamic Log Level Control** *(September 22, 2025)*
**Problem**: Log level changes required service restart, causing production downtime
- No way to debug production issues without interrupting service
- Debugging required stopping bot, changing config, and restarting
- Lost ability to investigate transient issues in real-time

**Solution**: Runtime log level control without restart
- **Added** `chatd-loglevel` command supporting all 5 log levels
- **Implemented** SIGHUP signal handler for instant level changes
- **Created** Docker-compatible file-based communication system
- **Simplified** implementation with clean, direct level setting

**Impact**:
- [x] **Instant debugging**: Change to DEBUG level without any service interruption
- [x] **Production troubleshooting**: Investigate live issues immediately
- [x] **Professional interface**: `sudo chatd-loglevel debug` provides immediate verbose logging
- [x] **Full control**: Support for debug/info/warning/error/critical levels
- [x] **Zero downtime**: Maintain service availability during troubleshooting

**Commands Available**:
```bash
sudo chatd-loglevel debug     # Maximum verbosity for troubleshooting
sudo chatd-loglevel info      # Normal operational messages  
sudo chatd-loglevel warning   # Warnings and errors only
sudo chatd-loglevel error     # Error conditions only
sudo chatd-loglevel critical  # Critical failures only
```

**Files Modified**: `chatd/logging_utils.py`, `scripts/create-management-scripts.sh`

### **Configurable Date Filtering** *(September 21, 2025)*
**Problem**: Hardcoded 5-day role filtering preventing flexible deployment configurations
- No way to adjust filtering without code changes
- Different environments might need different filtering windows
- Operational inflexibility for various use cases

**Solution**: Environment variable configuration with validation
- **Added** `MAX_POST_AGE_DAYS` environment variable (default: 5)
- **Implemented** 1-30 day range validation with helpful error messages
- **Enhanced** logging to show configured max age in debug output
- **Maintained** backward compatibility with existing behavior

**Impact**: 
- [x] Flexible role filtering based on deployment needs
- [x] Prevents spam from old bulk updates (configurable threshold)
- [x] No code changes required for operational adjustments
- [x] Clear validation prevents misconfiguration

**Files Modified**: `chatd/config.py`, `chatd/bot.py`, `.env.example`

### **Docker Build Performance Optimization** *(September 21, 2025)*
**Problem**: Slow deployments due to Docker rebuilding on every service restart
- `systemctl start` triggered full Docker rebuild (~4+ minutes)
- No separation between building images and deploying containers
- Made development iterations painfully slow

**Solution**: Separated build and deployment phases
- **Removed** Docker build from systemd service startup process
- **Added** dedicated management commands: `chatd build`, `chatd deploy`, `chatd update`
- **Optimized** deployment workflow for development speed

**Impact**: 
- [x] Deployment time reduced from ~4+ minutes to ~8 seconds
- [x] Build once, deploy multiple times capability
- [x] Faster iteration cycles for development and testing
- [x] Clear separation of concerns (build vs deploy)

**Files Modified**: `chatd-internships.service`, `scripts/create-management-scripts.sh`

### **ID-Based Role Tracking Implementation** *(September 24, 2025)*
**Problem**: Complex composite key matching system caused reliability issues
- Over-matching prevented detection of role re-openings
- Complex `get_role_id()` function with 28 lines of normalization logic
- Potential for matching ambiguity and missed notifications

**Solution**: Direct UUID-based tracking from listings.json
- **Migrated** from composite keys to direct `role['id']` access
- **Eliminated** complex `get_role_id()` and `normalize_role_key()` functions entirely
- **Implemented** comprehensive migration script for production data
- **Enhanced** management scripts with user-agnostic build process

**Impact**:
- [x] **100% reliable tracking**: Direct UUID access eliminates matching ambiguity
- [x] **Simplified codebase**: Removed 50+ lines of complex matching code  
- [x] **Production deployment**: Successfully migrated 319/325 messages (98.2% success)
- [x] **Future-proof architecture**: Scales with listings.json growth without complexity
- [x] **Enhanced tooling**: User-agnostic build system with CHATD_BRANCH support

**Migration Results**:
```
✅ Production data migration completed
   • Messages migrated: 319/325 (98.2% success rate)
   • Backup created: message_tracking.json.backup.1758770169
   • 6 unmigrated messages: likely obsolete roles no longer in listings.json
```

**Files Modified**: `chatd/repo.py`, `chatd/bot.py`, `scripts/migrate-to-id-keys.py`, `scripts/create-management-scripts.sh`

---

## 📊 Progress Tracking

- [x] **Critical Architectural Improvements**: 1/1 ✅ (ID-based role tracking)
- [x] **Performance Improvements**: 1/1 ✅ (Docker build optimization) 
- [x] **Configuration Enhancements**: 2/2 ✅ (Configurable date filtering, configuration validation)
- [x] **Operational Improvements**: 1/1 ✅ (Dynamic log level control)
- [ ] **Infrastructure Projects**: 0/4 (Docker auto-pruning, multi-environment support, enhanced test simulation, monitoring dashboard)
- [ ] **Feature Enhancements**: 0/4 (Async reactions, smart reactions, role status management, enhanced monitoring)
- [x] **Items Completed**: 5/15 ✅ (Docker optimization, date filtering, log level control, config validation, ID-based tracking)
- [ ] **Total Sub-tasks**: 35/70+ completed

**Immediate Quick Wins** 🚀:
- Docker Image Auto-Pruning (can be implemented now, will free up disk space immediately)

**Blocked by Disk Migration**:
- Multi-Environment Support (requires ~15-20GB disk space, currently have 7GB total)
- Enhanced Test Simulation Framework (depends on multi-environment setup)
- Monitoring Dashboard & Alerting System (requires ~3-5GB additional space for monitoring stack)

*Last Updated: September 25, 2025*
