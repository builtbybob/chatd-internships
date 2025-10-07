#!/bin/bash

###############################################################
# ChatD Environment Setup Script
# Creates isolated ChatD environments with unique naming
###############################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Usage function
usage() {
    echo "Usage: $0 <environment-name>"
    echo ""
    echo "Creates a new ChatD environment with isolated containers, database, and management."
    echo ""
    echo "Examples:"
    echo "  $0 thatd-internships     # Creates /opt/thatd-internships (development)"
    echo "  $0 newgrad-roles         # Creates /opt/newgrad-roles (new grad jobs)"
    echo "  $0 chatd-fall2025        # Creates /opt/chatd-fall2025 (seasonal)"
    echo ""
    echo "The script will:"
    echo "  - Create /opt/<environment-name>/ directory"
    echo "  - Prompt for Discord bot configuration"
    echo "  - Prompt for repository URL and ChatD branch"
    echo "  - Clone ChatD repository with specified branch"
    echo "  - Setup isolated Docker containers with <environment-name> prefix"
    echo "  - Assign unique ports automatically"
    echo "  - Create environment-specific systemd service"
    echo "  - Generate management command: /usr/local/bin/<environment-name>"
    exit 1
}

# Check arguments
if [[ $# -ne 1 ]]; then
    usage
fi

ENV_NAME="$1"
ENV_DIR="/opt/$ENV_NAME"

# Validate environment name
if [[ ! "$ENV_NAME" =~ ^[a-z0-9][a-z0-9-]*[a-z0-9]$ ]] && [[ ! "$ENV_NAME" =~ ^[a-z0-9]$ ]]; then
    echo -e "${RED}❌ Invalid environment name: $ENV_NAME${NC}"
    echo "Environment name must:"
    echo "  - Start and end with alphanumeric characters"
    echo "  - Contain only lowercase letters, numbers, and hyphens"
    echo "  - Examples: thatd-internships, newgrad-roles, chatd-dev"
    exit 1
fi

# Check if environment already exists
if [[ -d "$ENV_DIR" ]]; then
    echo -e "${RED}❌ Environment '$ENV_NAME' already exists at $ENV_DIR${NC}"
    echo "Use a different name or remove the existing environment first."
    exit 1
fi

# Check if we're running from the correct repository (optional check)
if [[ -f "$REPO_DIR/chatd/bot.py" ]] && [[ -f "$REPO_DIR/sql/init/001_initial_schema.sql" ]]; then
    echo -e "${GREEN}✅ Running from ChatD repository${NC}"
elif git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Warning: Not running from a ChatD repository${NC}"
    echo "Some features may not work correctly. Consider running from the chatd-internships repository."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
else
    echo -e "${BLUE}ℹ️  Running standalone (not in a git repository)${NC}"
fi

# Function to generate a secure password
generate_password() {
    # Generate a 32-character password with letters, numbers, and safe symbols
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Function to find next available port
find_available_port() {
    local base_port=$1
    local port=$base_port
    
    while ss -tuln | grep -q ":$port "; do
        ((port++))
    done
    
    echo $port
}

# Assign unique ports
POSTGRES_PORT=$(find_available_port 5432)
if [[ $POSTGRES_PORT == 5432 ]]; then
    # If 5432 is available, use 5433 to avoid conflicts with template
    POSTGRES_PORT=5433
fi

WEB_PORT=$(find_available_port 8080)
if [[ $WEB_PORT == 8080 ]]; then
    # If 8080 is available, use 8081 to avoid conflicts
    WEB_PORT=8081
fi

# Generate secure database password
DB_PASSWORD=$(generate_password)

echo ""
echo -e "${YELLOW}📝 Discord Bot Configuration${NC}"
echo "Please provide your Discord bot details for this environment."
echo ""

# Prompt for Discord bot token
while true; do
    echo -e "${BLUE}🤖 Discord Bot Token:${NC}"
    echo "  (Get this from https://discord.com/developers/applications)"
    read -p "Enter Discord bot token: " DISCORD_TOKEN
    
    if [[ -z "$DISCORD_TOKEN" ]]; then
        echo -e "${RED}❌ Discord bot token cannot be empty. Please try again.${NC}"
        continue
    fi
    
    # Basic validation - Discord bot tokens are typically 70+ characters
    if [[ ${#DISCORD_TOKEN} -lt 50 ]]; then
        echo -e "${RED}❌ Discord bot token seems too short (expected 50+ characters). Please verify.${NC}"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            continue
        fi
    fi
    
    break
done

echo ""

# Prompt for channel IDs
while true; do
    echo -e "${BLUE}📺 Discord Channel IDs:${NC}"
    echo "  (Right-click on channels → Copy ID, separate multiple IDs with commas)"
    echo "  Example: 123456789012345678,987654321098765432"
    read -p "Enter channel ID(s): " CHANNEL_IDS
    
    if [[ -z "$CHANNEL_IDS" ]]; then
        echo -e "${RED}❌ At least one channel ID is required. Please try again.${NC}"
        continue
    fi
    
    # Basic validation - check if IDs look like Discord snowflakes
    IFS=',' read -ra CHANNEL_ARRAY <<< "$CHANNEL_IDS"
    VALID_CHANNELS=true
    
    for channel_id in "${CHANNEL_ARRAY[@]}"; do
        # Remove whitespace
        channel_id=$(echo "$channel_id" | tr -d ' ')
        
        # Check if it's a number and has reasonable length (Discord IDs are 17-19 digits)
        if [[ ! "$channel_id" =~ ^[0-9]{16,20}$ ]]; then
            echo -e "${RED}❌ Invalid channel ID: $channel_id (should be 16-20 digits)${NC}"
            VALID_CHANNELS=false
            break
        fi
    done
    
    if [[ "$VALID_CHANNELS" == true ]]; then
        # Clean up the channel IDs (remove extra spaces)
        CHANNEL_IDS=$(echo "$CHANNEL_IDS" | tr -d ' ')
        break
    else
        echo "Please check your channel IDs and try again."
    fi
done

echo ""

# Prompt for repository URL
echo -e "${BLUE}📦 Repository URL:${NC}"
echo "  (The GitHub repository containing internship listings)"
echo "  Default: https://github.com/SimplifyJobs/Summer2026-Internships.git"
read -p "Enter repository URL (or press Enter for default): " REPO_URL_INPUT

if [[ -z "$REPO_URL_INPUT" ]]; then
    REPO_URL="https://github.com/SimplifyJobs/Summer2026-Internships.git"
    echo -e "${GREEN}✅ Using default repository URL${NC}"
else
    REPO_URL="$REPO_URL_INPUT"
    
    # Basic validation - check if it looks like a git URL
    if [[ ! "$REPO_URL" =~ ^https?://.*\.git$ ]] && [[ ! "$REPO_URL" =~ ^git@.*\.git$ ]]; then
        echo -e "${YELLOW}⚠️  Repository URL doesn't look like a standard git URL${NC}"
        echo "  Expected format: https://github.com/user/repo.git"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Setup cancelled."
            exit 0
        fi
    fi
fi

echo ""

# Prompt for ChatD branch
echo -e "${BLUE}🌿 ChatD Branch:${NC}"
# Try to detect current branch, fallback to main if not in a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
    echo "  (The branch of chatd-internships repository to clone)"
    echo "  Current branch: $CURRENT_BRANCH"
else
    CURRENT_BRANCH="main"
    echo "  (The branch of chatd-internships repository to clone)"
    echo "  Default branch: $CURRENT_BRANCH (not in a git repository)"
fi
read -p "Enter branch name (or press Enter for $CURRENT_BRANCH): " BRANCH_INPUT

if [[ -z "$BRANCH_INPUT" ]]; then
    CHATD_BRANCH="$CURRENT_BRANCH"
    echo -e "${GREEN}✅ Using branch: $CHATD_BRANCH${NC}"
else
    CHATD_BRANCH="$BRANCH_INPUT"
    echo -e "${GREEN}✅ Using specified branch: $CHATD_BRANCH${NC}"
fi

echo ""
echo -e "${GREEN}✅ Configuration collected:${NC}"
echo -e "  🤖 Bot token: ${DISCORD_TOKEN:0:20}...***"
echo -e "  📺 Channel(s): $CHANNEL_IDS"
echo -e "  📦 Repository: $REPO_URL"
echo -e "  🌿 ChatD Branch: $CHATD_BRANCH"
echo -e "  🔒 Database password: [Generated securely]"
echo ""

# Create environment directory by cloning chatd-internships
echo -e "${YELLOW}📁 Creating environment by cloning ChatD repository...${NC}"

# Determine the repository URL for chatd-internships
if git rev-parse --git-dir > /dev/null 2>&1; then
    CHATD_REPO_URL=$(git remote get-url origin 2>/dev/null || echo "https://github.com/builtbybob/chatd-internships.git")
else
    CHATD_REPO_URL="https://github.com/builtbybob/chatd-internships.git"
fi

echo -e "${BLUE}📦 Repository: $CHATD_REPO_URL${NC}"
echo -e "${BLUE}🌿 Branch: $CHATD_BRANCH${NC}"

if ! sudo git clone -b "$CHATD_BRANCH" "$CHATD_REPO_URL" "$ENV_DIR"; then
    echo -e "${RED}❌ Failed to clone ChatD repository to $ENV_DIR${NC}"
    echo "This creates the environment directory with all necessary scripts."
    exit 1
fi

# Create additional directories
sudo mkdir -p "$ENV_DIR/data" "$ENV_DIR/logs"

# Set proper ownership for Docker containers (run as user 1000) - data and logs only for now
sudo chown -R 1000:1000 "$ENV_DIR/data" "$ENV_DIR/logs"
echo -e "${GREEN}✅ Environment directory created with ChatD repository${NC}"

echo ""
echo -e "${BLUE}🚀 Setting up ChatD environment: $ENV_NAME${NC}"
echo -e "${BLUE}📁 Directory: $ENV_DIR${NC}"
echo -e "${BLUE}🐳 Container prefix: $ENV_NAME${NC}"
echo -e "${BLUE}🔌 PostgreSQL port: $POSTGRES_PORT${NC}"
echo -e "${BLUE}🌐 Web port: $WEB_PORT${NC}"
echo -e "${BLUE}🔒 Database password: [Generated securely]${NC}"
echo ""

# Confirm before proceeding
read -p "Continue with setup? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Clone repository
echo -e "${YELLOW}📥 Cloning repository...${NC}"
REPO_DIR_NAME="Summer2026-Internships"
if [[ ! -d "$ENV_DIR/$REPO_DIR_NAME" ]]; then
    if ! sudo git clone "$REPO_URL" "$ENV_DIR/$REPO_DIR_NAME"; then
        echo -e "${RED}❌ Failed to clone repository: $REPO_URL${NC}"
        echo "Please check the repository URL and your internet connection."
        exit 1
    fi
    echo -e "${GREEN}✅ Repository cloned successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Repository directory already exists, skipping clone${NC}"
fi

# Set proper ownership for the cloned repository (Docker containers run as user 1000)
sudo chown -R 1000:1000 "$ENV_DIR/$REPO_DIR_NAME"

# Copy and customize docker-compose.yml
echo -e "${YELLOW}🐳 Setting up Docker configuration...${NC}"
cat > "/tmp/docker-compose-$ENV_NAME.yml" << EOF
version: '3.8'

services:
  ${ENV_NAME}-postgres:
    image: postgres:15-alpine
    container_name: ${ENV_NAME}-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${ENV_NAME//-/_}
      POSTGRES_USER: ${ENV_NAME//-/_}
      POSTGRES_PASSWORD: \${DB_PASSWORD}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"
    volumes:
      - ${ENV_NAME}_postgres_data:/var/lib/postgresql/data
      - $ENV_DIR/sql/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "${POSTGRES_PORT}:5432"
    networks:
      - ${ENV_NAME}-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${POSTGRES_USER:-${ENV_NAME//-/_}} -d \${POSTGRES_DB:-${ENV_NAME//-/_}}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  ${ENV_NAME}-bot:
    build:
      context: $ENV_DIR
      dockerfile: Dockerfile
    container_name: ${ENV_NAME}-bot
    restart: unless-stopped
    depends_on:
      ${ENV_NAME}-postgres:
        condition: service_healthy
    environment:
      - DB_HOST=${ENV_NAME}-postgres
      - DB_NAME=${ENV_NAME//-/_}
      - DB_USER=${ENV_NAME//-/_}
    env_file:
      - .env
    volumes:
      - $ENV_DIR/Summer2026-Internships:/app/Summer2026-Internships
      - ${ENV_NAME}_app_data:/app/data
      - $ENV_DIR/logs:/app/logs
      # Mount timezone data for proper local time
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
    networks:
      - ${ENV_NAME}-network
    healthcheck:
      test: ["CMD", "python3", "-c", "import os; exit(0 if os.path.exists('/app/main.py') else 1)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  ${ENV_NAME}-network:
    name: ${ENV_NAME}-network
    driver: bridge

volumes:
  ${ENV_NAME}_postgres_data:
    name: ${ENV_NAME}_postgres_data
  ${ENV_NAME}_app_data:
    name: ${ENV_NAME}_app_data
EOF

sudo mv "/tmp/docker-compose-$ENV_NAME.yml" "$ENV_DIR/docker-compose.yml"

# Create template .env file
echo -e "${YELLOW}⚙️  Creating environment configuration...${NC}"
cat > "/tmp/.env-$ENV_NAME" << EOF
###############################################################
# ChatD Environment: $ENV_NAME
# Auto-generated on $(date)
###############################################################

###############################################################
# Discord Bot Configuration (REQUIRED)
###############################################################

# Discord bot token for $ENV_NAME environment
DISCORD_TOKEN=$DISCORD_TOKEN

# Comma-separated Discord channel IDs for $ENV_NAME
CHANNEL_IDS=$CHANNEL_IDS

###############################################################
# Database Configuration
###############################################################

# Database password for $ENV_NAME environment
DB_PASSWORD=$DB_PASSWORD

# Database configuration (auto-configured by Docker)
DB_TYPE=postgresql
DB_HOST=${ENV_NAME}-postgres
DB_PORT=5432
DB_NAME=${ENV_NAME//-/_}
DB_USER=${ENV_NAME//-/_}
MIGRATION_MODE=database_only

###############################################################
# Repository Settings
###############################################################

REPO_URL=$REPO_URL
LOCAL_REPO_PATH=/app/Summer2026-Internships

###############################################################
# Performance Settings (from Section 4.1)
###############################################################

MESSAGE_POST_DELAY_MS=100
REACTION_DELAY_MS=500
BATCH_PROCESSING_DELAY_MS=50

###############################################################
# Environment Settings
###############################################################

LOG_LEVEL=INFO
ENABLE_REACTIONS=true
MAX_RETRIES=3
CHECK_INTERVAL_MINUTES=1
MAX_POST_AGE_DAYS=3

# Environment-specific settings
DB_CONNECTION_POOL_SIZE=5
DB_AUTO_VACUUM=true
DB_HEALTH_CHECK_INTERVAL=300
DB_MIGRATION_BATCH_SIZE=100
DB_BACKUP_RETENTION_DAYS=30
EOF

sudo mv "/tmp/.env-$ENV_NAME" "$ENV_DIR/.env"
sudo chown $USER:docker "$ENV_DIR/.env"  # Match user ownership like production
sudo chmod 600 "$ENV_DIR/.env"  # Secure environment file

# Build Docker images (after .env file is in place)
echo -e "${YELLOW}🔨 Building Docker images...${NC}"
cd "$ENV_DIR"
if ! sudo docker-compose build; then
    echo -e "${RED}❌ Failed to build Docker images${NC}"
    echo "Please check the Dockerfile and requirements.txt, then try manually:"
    echo "  cd $ENV_DIR && docker-compose build"
    exit 1
fi
echo -e "${GREEN}✅ Docker images built successfully${NC}"

# Create systemd service
echo -e "${YELLOW}🔧 Creating systemd service...${NC}"

# Determine which Docker Compose command to use
if command -v docker-compose &> /dev/null; then
    COMPOSE_EXEC="/usr/bin/docker-compose"
    COMPOSE_ARGS=""
    COMPOSE_CMD_START="$COMPOSE_EXEC up -d"
    COMPOSE_CMD_STOP="$COMPOSE_EXEC down"
    COMPOSE_CMD_RESTART="$COMPOSE_EXEC restart"
elif docker compose version &> /dev/null; then
    COMPOSE_EXEC="/usr/bin/docker"
    COMPOSE_ARGS="compose"
    COMPOSE_CMD_START="$COMPOSE_EXEC $COMPOSE_ARGS up -d"
    COMPOSE_CMD_STOP="$COMPOSE_EXEC $COMPOSE_ARGS down"
    COMPOSE_CMD_RESTART="$COMPOSE_EXEC $COMPOSE_ARGS restart"
else
    echo -e "${RED}❌ Neither docker-compose nor docker compose found${NC}"
    echo "Please install Docker Compose and try again."
    exit 1
fi

cat > "/tmp/$ENV_NAME.service" << EOF
[Unit]
Description=ChatD Bot - $ENV_NAME Environment
Documentation=https://github.com/builtbybob/chatd-internships
After=docker.service network.target
Requires=docker.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Group=root
TimeoutStartSec=300
TimeoutStopSec=30
WorkingDirectory=$ENV_DIR

# Create data directories if they don't exist
ExecStartPre=/bin/mkdir -p $ENV_DIR/data $ENV_DIR/logs
ExecStartPre=/bin/chown -R 1000:1000 $ENV_DIR/data $ENV_DIR/logs

# Stop any existing containers
ExecStartPre=-/usr/bin/docker-compose down --remove-orphans

# Start services with docker-compose (both bot and PostgreSQL)
ExecStart=/usr/bin/docker-compose up -d

# Health check for bot container
ExecStartPost=/bin/sleep 15
ExecStartPost=/usr/bin/docker exec ${ENV_NAME}-bot python -c "import sys; sys.exit(0)"

# Stop all services when systemd stops the service
ExecStop=/usr/bin/docker-compose down

# Reload services (restart containers)
ExecReload=/usr/bin/docker-compose restart

[Install]
WantedBy=multi-user.target
EOF

sudo mv "/tmp/$ENV_NAME.service" "/etc/systemd/system/$ENV_NAME.service"

# Create management script
echo -e "${YELLOW}🛠️  Creating management command...${NC}"
cat > "/tmp/$ENV_NAME-mgmt" << 'MGMT_SCRIPT_EOF'
#!/bin/bash

###############################################################
# ChatD Environment Management Script
# Environment: ENV_NAME_PLACEHOLDER
###############################################################

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENV_NAME="ENV_NAME_PLACEHOLDER"
ENV_DIR="/opt/$ENV_NAME"
SERVICE_NAME="$ENV_NAME.service"

# Determine which Docker Compose command to use
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Neither docker-compose nor docker compose found${NC}"
    exit 1
fi

# Check if we're in the right directory
if [[ ! -d "$ENV_DIR" ]]; then
    echo -e "${RED}❌ Environment directory not found: $ENV_DIR${NC}"
    exit 1
fi

cd "$ENV_DIR"

case "${1:-}" in
    "status")
        echo -e "${BLUE}📊 $ENV_NAME Environment Status${NC}"
        echo "=================================="
        echo ""
        echo -e "${YELLOW}🔧 Systemd Service:${NC}"
        sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
        echo ""
        echo -e "${YELLOW}🐳 Docker Containers:${NC}"
        $DOCKER_COMPOSE_CMD ps
        echo ""
        echo -e "${YELLOW}💾 Database Status:${NC}"
        $DOCKER_COMPOSE_CMD exec ${ENV_NAME}-postgres pg_isready -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_} 2>/dev/null && echo "✅ Database is ready" || echo "❌ Database not accessible"
        ;;
    "logs")
        CONTAINER="${2:-}"
        if [[ -n "$CONTAINER" ]]; then
            echo -e "${BLUE}📋 Logs for $ENV_NAME-$CONTAINER${NC}"
            $DOCKER_COMPOSE_CMD logs -f "${ENV_NAME}-${CONTAINER}"
        else
            echo -e "${BLUE}📋 All logs for $ENV_NAME${NC}"
            $DOCKER_COMPOSE_CMD logs -f
        fi
        ;;
    "start")
        echo -e "${GREEN}🚀 Starting $ENV_NAME environment...${NC}"
        sudo systemctl start "$SERVICE_NAME"
        ;;
    "stop")
        echo -e "${YELLOW}🛑 Stopping $ENV_NAME environment...${NC}"
        sudo systemctl stop "$SERVICE_NAME"
        ;;
    "restart")
        echo -e "${BLUE}🔄 Restarting $ENV_NAME environment...${NC}"
        sudo systemctl restart "$SERVICE_NAME"
        ;;
    "enable")
        echo -e "${GREEN}🔧 Enabling $ENV_NAME to start on boot...${NC}"
        sudo systemctl enable "$SERVICE_NAME"
        ;;
    "disable")
        echo -e "${YELLOW}🔧 Disabling $ENV_NAME auto-start...${NC}"
        sudo systemctl disable "$SERVICE_NAME"
        ;;
    "build")
        echo -e "${BLUE}🔨 Building $ENV_NAME containers...${NC}"
        $DOCKER_COMPOSE_CMD build
        ;;
    "pull")
        echo -e "${BLUE}📥 Pulling latest images for $ENV_NAME...${NC}"
        $DOCKER_COMPOSE_CMD pull
        ;;
    "shell")
        CONTAINER="${2:-bot}"
        echo -e "${BLUE}🐚 Opening shell in $ENV_NAME-$CONTAINER...${NC}"
        $DOCKER_COMPOSE_CMD exec "${ENV_NAME}-${CONTAINER}" /bin/bash
        ;;
    "db")
        echo -e "${BLUE}🗄️  Connecting to $ENV_NAME database...${NC}"
        $DOCKER_COMPOSE_CMD exec ${ENV_NAME}-postgres psql -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_}
        ;;
    "update")
        echo -e "${BLUE}🔄 Updating $ENV_NAME environment...${NC}"
        echo "Pulling latest code..."
        $DOCKER_COMPOSE_CMD pull
        echo "Rebuilding containers..."
        $DOCKER_COMPOSE_CMD build
        echo "Restarting services..."
        $DOCKER_COMPOSE_CMD up -d
        ;;
    "cleanup")
        echo -e "${YELLOW}🧹 Cleaning up $ENV_NAME Docker resources...${NC}"
        $DOCKER_COMPOSE_CMD down
        echo "Removing unused images..."
        docker image prune -f
        echo "Removing unused volumes (excluding data)..."
        docker volume prune -f
        ;;
    *)
        echo "Usage: $ENV_NAME <command>"
        echo ""
        echo "Environment Management:"
        echo "  status              Show environment status"
        echo "  start               Start the environment"
        echo "  stop                Stop the environment"
        echo "  restart             Restart the environment"
        echo "  enable              Enable auto-start on boot"
        echo "  disable             Disable auto-start"
        echo ""
        echo "Container Management:"
        echo "  logs [container]    Show logs (bot, postgres, or all)"
        echo "  build               Build containers"
        echo "  pull                Pull latest images"
        echo "  shell [container]   Open shell (default: bot)"
        echo "  update              Pull, build, and restart"
        echo ""
        echo "Database:"
        echo "  db                  Connect to PostgreSQL"
        echo ""
        echo "Maintenance:"
        echo "  cleanup             Clean up Docker resources"
        echo ""
        echo "Examples:"
        echo "  $ENV_NAME status"
        echo "  $ENV_NAME logs bot"
        echo "  $ENV_NAME shell postgres"
        echo "  $ENV_NAME db"
        ;;
esac
MGMT_SCRIPT_EOF

# Replace placeholder in the management script
sed "s/ENV_NAME_PLACEHOLDER/$ENV_NAME/g" "/tmp/$ENV_NAME-mgmt" > "/tmp/$ENV_NAME-final"
sudo mv "/tmp/$ENV_NAME-final" "/usr/local/bin/$ENV_NAME"
sudo chmod +x "/usr/local/bin/$ENV_NAME"
sudo rm -f "/tmp/$ENV_NAME-mgmt"

# Set ownership and permissions
echo -e "${YELLOW}🔐 Setting permissions...${NC}"
sudo chown -R root:root "$ENV_DIR"
# Restore proper ownership for Docker container directories
sudo chown -R 1000:1000 "$ENV_DIR/data" "$ENV_DIR/logs" "$ENV_DIR/$REPO_DIR_NAME"
sudo chmod 755 "$ENV_DIR"
sudo chmod 644 "$ENV_DIR/docker-compose.yml"
sudo chmod 600 "$ENV_DIR/.env"  # Secure environment file

echo ""
# Database Migration (Optional)
echo ""
echo -e "${CYAN}📊 Database Migration${NC}"
echo "The system can automatically migrate data from listings.json to the database."
read -p "Would you like to migrate existing data to the database? (y/n): " -n 1 -r MIGRATE_DATA
echo ""

if [[ $MIGRATE_DATA =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}🔄 Starting database migration...${NC}"
    
    # Check if repository was cloned and has listings.json
    CLONED_REPO_PATH="$ENV_DIR/$REPO_DIR_NAME"
    LISTINGS_JSON_PATH="$CLONED_REPO_PATH/.github/scripts/listings.json"
    if [[ ! -f "$LISTINGS_JSON_PATH" ]]; then
        echo -e "${YELLOW}⚠️  Warning: listings.json not found at $LISTINGS_JSON_PATH${NC}"
        echo "Migration will be skipped. You can run it manually later."
        echo "To run manually: python3 scripts/migrate_json_to_database.py --repo-path '$CLONED_REPO_PATH'"
    else
        # Create Python virtual environment for migration
        echo -e "${BLUE}📦 Setting up Python environment...${NC}"
        VENV_DIR="$ENV_DIR/.venv"
        
        if ! python3 -m venv "$VENV_DIR"; then
            echo -e "${RED}❌ Failed to create Python virtual environment${NC}"
            echo "Please install python3-venv package: sudo apt-get install python3-venv"
            echo "Migration will be skipped."
        else
            # Activate virtual environment and install requirements
            source "$VENV_DIR/bin/activate"
            
            echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
            if pip install -r "$ENV_DIR/requirements.txt" > /dev/null 2>&1; then
                
                # Start only the database for migration (not the bot!)
                echo -e "${BLUE}🚀 Starting database for migration...${NC}"
                cd "$ENV_DIR"
                
                # Check if docker-compose or docker compose is available
                if command -v docker-compose &> /dev/null; then
                    DOCKER_COMPOSE_CMD="docker-compose"
                elif docker compose version &> /dev/null; then
                    DOCKER_COMPOSE_CMD="docker compose"
                else
                    echo -e "${RED}❌ Neither docker-compose nor docker compose found${NC}"
                    echo "Migration will be skipped. Please install Docker Compose."
                    echo "You can retry manually: python3 scripts/migrate_json_to_database.py --repo-path '$CLONED_REPO_PATH'"
                    deactivate
                fi
                
                if ! sudo $DOCKER_COMPOSE_CMD up -d "$ENV_NAME-postgres"; then
                    echo -e "${RED}❌ Failed to start database container${NC}"
                    echo "Migration will be skipped. Check Docker logs for details."
                    echo "You can retry manually: python3 scripts/migrate_json_to_database.py --repo-path '$CLONED_REPO_PATH'"
                else
                    echo -e "${BLUE}⏳ Waiting for database to be ready...${NC}"
                    # Wait for database container to be healthy (up to 60 seconds)
                    WAIT_COUNT=0
                    while [ $WAIT_COUNT -lt 60 ]; do
                        if sudo $DOCKER_COMPOSE_CMD ps "$ENV_NAME-postgres" | grep -q "healthy"; then
                            echo -e "${GREEN}✅ Database is ready!${NC}"
                            break
                        fi
                        echo -n "."
                        sleep 1
                        WAIT_COUNT=$((WAIT_COUNT + 1))
                    done
                    
                    if [ $WAIT_COUNT -ge 60 ]; then
                        echo -e "${YELLOW}⚠️  Database health check timed out, proceeding anyway...${NC}"
                    fi
                    
                    # Run migration
                    echo -e "${BLUE}🗃️  Running migration script...${NC}"
                    # Run the migration script from the environment's chatd repository
                    cd "$ENV_DIR"
                    # Use the venv's Python executable with sudo to access both packages and secure .env file
                    if sudo DOCKER_CONTAINER=false DB_PORT="$POSTGRES_PORT" "$VENV_DIR/bin/python3" scripts/migrate_json_to_database.py --repo-path "$CLONED_REPO_PATH"; then
                        echo -e "${GREEN}✅ Database migration completed successfully!${NC}"
                        echo -e "${BLUE}ℹ️  Database is ready with migrated data. Start the full environment when ready: $ENV_NAME start${NC}"
                    else
                        echo -e "${YELLOW}⚠️  Migration encountered issues. Check logs for details.${NC}"
                        echo "You can retry manually from $ENV_DIR: python3 scripts/migrate_json_to_database.py --repo-path '$CLONED_REPO_PATH'"
                    fi
                    
                    # Stop only the database (bot was never started)
                    echo -e "${BLUE}🛑 Stopping database...${NC}"
                    cd "$ENV_DIR" && sudo $DOCKER_COMPOSE_CMD stop "$ENV_NAME-postgres" > /dev/null 2>&1
                fi
            else
                echo -e "${RED}❌ Failed to install Python requirements${NC}"
                echo "Migration will be skipped. Install requirements manually and run:"
                echo "python3 scripts/migrate_json_to_database.py --repo-path '$CLONED_REPO_PATH'"
            fi
            
            deactivate
        fi
    fi
else
    echo -e "${BLUE}ℹ️  Skipping database migration.${NC}"
    echo "You can run it later with: python3 scripts/migrate_json_to_database.py --repo-path '$CLONED_REPO_PATH'"
fi

# Reload systemd after all service files are finalized
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}✅ ChatD environment '$ENV_NAME' has been created successfully!${NC}"
echo ""
echo -e "${BLUE}📁 Location:${NC} $ENV_DIR"
echo -e "${BLUE}🐳 Containers:${NC} ${ENV_NAME}-postgres, ${ENV_NAME}-bot"
echo -e "${BLUE}🔌 PostgreSQL Port:${NC} $POSTGRES_PORT"
echo -e "${BLUE}� Database Password:${NC} Auto-generated and configured"
echo -e "${BLUE}�🛠️  Management Command:${NC} $ENV_NAME"
echo -e "${BLUE}🔧 Systemd Service:${NC} $ENV_NAME.service"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Configuration is fully complete! ✅"
echo "2. Start the environment: $ENV_NAME start"
echo "3. Enable auto-start: $ENV_NAME enable"
echo "4. Check status: $ENV_NAME status"
echo ""
echo -e "${GREEN}🎉 Your environment is ready to use immediately!${NC}"
echo ""
echo -e "${YELLOW}🎯 Quick Commands:${NC}"
echo "  $ENV_NAME status    # Check environment status"
echo "  $ENV_NAME logs      # View all logs"
echo "  $ENV_NAME db        # Connect to database"
echo "  $ENV_NAME shell     # Open bot container shell"
echo ""
echo -e "${GREEN}Environment is ready for configuration!${NC}"