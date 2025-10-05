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

# Check if we're running from the correct repository
if [[ ! -f "$REPO_DIR/chatd/bot.py" ]] || [[ ! -f "$REPO_DIR/sql/init/001_initial_schema.sql" ]]; then
    echo -e "${RED}❌ This script must be run from a ChatD repository${NC}"
    echo "Missing required files: chatd/bot.py or sql/init/001_initial_schema.sql"
    echo "Please run this script from the chatd-internships repository directory."
    exit 1
fi

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

echo -e "${BLUE}🚀 Setting up ChatD environment: $ENV_NAME${NC}"
echo -e "${BLUE}📁 Directory: $ENV_DIR${NC}"
echo -e "${BLUE}🐳 Container prefix: $ENV_NAME${NC}"
echo -e "${BLUE}🔌 PostgreSQL port: $POSTGRES_PORT${NC}"
echo -e "${BLUE}🌐 Web port: $WEB_PORT${NC}"
echo ""

# Confirm before proceeding
read -p "Continue with setup? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Create environment directory
echo -e "${YELLOW}📁 Creating environment directory...${NC}"
if ! sudo mkdir -p "$ENV_DIR" "$ENV_DIR/data" "$ENV_DIR/logs"; then
    echo -e "${RED}❌ Failed to create environment directory: $ENV_DIR${NC}"
    echo "Please check permissions and try again."
    exit 1
fi

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
      - $REPO_DIR/sql/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "${POSTGRES_PORT}:5432"
    networks:
      - ${ENV_NAME}-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${POSTGRES_USER:-${ENV_NAME//-/_}} -d \${POSTGRES_DB:-${ENV_NAME//-/_}}"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  ${ENV_NAME}-bot:
    build:
      context: $REPO_DIR
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
      - ${ENV_NAME}_repo_data:/app/Summer2026-Internships
      - ${ENV_NAME}_app_data:/app/data
      - $ENV_DIR/logs:/app/logs
    networks:
      - ${ENV_NAME}-network
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
  ${ENV_NAME}_repo_data:
    name: ${ENV_NAME}_repo_data
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
DISCORD_TOKEN=your_discord_bot_token_here

# Comma-separated Discord channel IDs for $ENV_NAME
CHANNEL_IDS=your_channel_ids_here

###############################################################
# Database Configuration
###############################################################

# Database password for $ENV_NAME environment
DB_PASSWORD=your_postgres_password_here

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

REPO_URL=https://github.com/SimplifyJobs/Summer2026-Internships.git
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

# Create systemd service
echo -e "${YELLOW}🔧 Creating systemd service...${NC}"
cat > "/tmp/$ENV_NAME.service" << EOF
[Unit]
Description=ChatD Bot - $ENV_NAME Environment
After=docker.service
Requires=docker.service
StartLimitIntervalSec=0

[Service]
Type=forking
Restart=always
RestartSec=10
User=root
Group=root
WorkingDirectory=$ENV_DIR

# Start the service
ExecStart=/usr/bin/docker compose up -d

# Stop the service
ExecStop=/usr/bin/docker compose down

# Reload the service
ExecReload=/usr/bin/docker compose restart

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
        docker compose ps
        echo ""
        echo -e "${YELLOW}💾 Database Status:${NC}"
        docker compose exec ${ENV_NAME}-postgres pg_isready -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_} 2>/dev/null && echo "✅ Database is ready" || echo "❌ Database not accessible"
        ;;
    "logs")
        CONTAINER="${2:-}"
        if [[ -n "$CONTAINER" ]]; then
            echo -e "${BLUE}📋 Logs for $ENV_NAME-$CONTAINER${NC}"
            docker compose logs -f "${ENV_NAME}-${CONTAINER}"
        else
            echo -e "${BLUE}📋 All logs for $ENV_NAME${NC}"
            docker compose logs -f
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
        docker compose build
        ;;
    "pull")
        echo -e "${BLUE}📥 Pulling latest images for $ENV_NAME...${NC}"
        docker compose pull
        ;;
    "shell")
        CONTAINER="${2:-bot}"
        echo -e "${BLUE}🐚 Opening shell in $ENV_NAME-$CONTAINER...${NC}"
        docker compose exec "${ENV_NAME}-${CONTAINER}" /bin/bash
        ;;
    "db")
        echo -e "${BLUE}🗄️  Connecting to $ENV_NAME database...${NC}"
        docker compose exec ${ENV_NAME}-postgres psql -U ${ENV_NAME//-/_} -d ${ENV_NAME//-/_}
        ;;
    "update")
        echo -e "${BLUE}🔄 Updating $ENV_NAME environment...${NC}"
        echo "Pulling latest code..."
        docker compose pull
        echo "Rebuilding containers..."
        docker compose build
        echo "Restarting services..."
        docker compose up -d
        ;;
    "cleanup")
        echo -e "${YELLOW}🧹 Cleaning up $ENV_NAME Docker resources...${NC}"
        docker compose down
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
sudo chmod 755 "$ENV_DIR"
sudo chmod 644 "$ENV_DIR/docker-compose.yml"
sudo chmod 600 "$ENV_DIR/.env"  # Secure environment file

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo -e "${GREEN}✅ ChatD environment '$ENV_NAME' has been created successfully!${NC}"
echo ""
echo -e "${BLUE}📁 Location:${NC} $ENV_DIR"
echo -e "${BLUE}🐳 Containers:${NC} ${ENV_NAME}-postgres, ${ENV_NAME}-bot"
echo -e "${BLUE}🔌 PostgreSQL Port:${NC} $POSTGRES_PORT"
echo -e "${BLUE}🛠️  Management Command:${NC} $ENV_NAME"
echo -e "${BLUE}🔧 Systemd Service:${NC} $ENV_NAME.service"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "1. Edit the configuration: sudo nano $ENV_DIR/.env"
echo "2. Set your Discord bot token and channel IDs"
echo "3. Set your database password"
echo "4. Start the environment: $ENV_NAME start"
echo "5. Enable auto-start: $ENV_NAME enable"
echo ""
echo -e "${YELLOW}🎯 Quick Commands:${NC}"
echo "  $ENV_NAME status    # Check environment status"
echo "  $ENV_NAME logs      # View all logs"
echo "  $ENV_NAME db        # Connect to database"
echo "  $ENV_NAME shell     # Open bot container shell"
echo ""
echo -e "${GREEN}Environment is ready for configuration!${NC}"