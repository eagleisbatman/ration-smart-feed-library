#!/bin/bash

# Feed Formulation Backend Deployment Script with Cron Setup
# This script deploys the application via Docker and sets up the cleanup cron job

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Update these variables for your server
APP_NAME="feed-formulation-be"
APP_DIR="/opt/feed-formulation-be"  # Update this to your actual deployment path
DOCKER_IMAGE_NAME="feed-formulation-backend"
DOCKER_CONTAINER_NAME="feed-formulation-app"
LOG_DIR="$APP_DIR/logs"
CRON_LOG_FILE="$LOG_DIR/cleanup.log"

echo -e "${BLUE}🚀 Starting Feed Formulation Backend Deployment${NC}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    print_warning "docker-compose not found. Using 'docker compose' (newer syntax)..."
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

print_status "Prerequisites check completed"

# Create necessary directories
print_info "Creating necessary directories..."
mkdir -p "$APP_DIR"
mkdir -p "$LOG_DIR"
print_status "Directories created"

# Stop and remove existing container if it exists
print_info "Stopping existing container..."
if docker ps -a --format 'table {{.Names}}' | grep -q "$DOCKER_CONTAINER_NAME"; then
    docker stop "$DOCKER_CONTAINER_NAME" || true
    docker rm "$DOCKER_CONTAINER_NAME" || true
    print_status "Existing container stopped and removed"
else
    print_info "No existing container found"
fi

# Build and start Docker container
print_info "Building and starting Docker container..."
cd "$APP_DIR"

# Build the Docker image
print_info "Building Docker image..."
docker build -t "$DOCKER_IMAGE_NAME" .

# Start the container
print_info "Starting container..."
docker run -d \
    --name "$DOCKER_CONTAINER_NAME" \
    --restart unless-stopped \
    -p 8000:8000 \
    -v "$APP_DIR/logs:/app/logs" \
    -v "$APP_DIR/.env:/app/.env" \
    --env-file .env \
    "$DOCKER_IMAGE_NAME"

print_status "Docker container started successfully"

# Wait for application to be ready
print_info "Waiting for application to be ready..."
sleep 10

# Check if application is running
if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    print_status "Application is running and healthy"
else
    print_warning "Application health check failed, but continuing with cron setup..."
fi

# Set up cron job
print_info "Setting up cron job for report cleanup..."

# Create the cron job entry
CRON_JOB="0 */3 * * * cd $APP_DIR && docker exec $DOCKER_CONTAINER_NAME python cleanup_old_reports.py >> $CRON_LOG_FILE 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "cleanup_old_reports.py"; then
    print_warning "Cron job already exists. Removing old entry..."
    # Remove existing cron job
    crontab -l 2>/dev/null | grep -v "cleanup_old_reports.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

print_status "Cron job added successfully"

# Verify cron job was added
print_info "Verifying cron job..."
if crontab -l | grep -q "cleanup_old_reports.py"; then
    print_status "Cron job verified successfully"
    echo -e "${BLUE}Cron job details:${NC}"
    crontab -l | grep "cleanup_old_reports.py"
else
    print_error "Failed to add cron job"
    exit 1
fi

# Test the cleanup script
print_info "Testing cleanup script..."
if docker exec "$DOCKER_CONTAINER_NAME" python cleanup_old_reports.py; then
    print_status "Cleanup script test successful"
else
    print_warning "Cleanup script test failed, but cron job is set up"
fi

# Set up log rotation for cleanup logs
print_info "Setting up log rotation..."
cat > /etc/logrotate.d/feed-formulation-cleanup << EOF
$CRON_LOG_FILE {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF

print_status "Log rotation configured"

# Final status
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}📋 Deployment Summary:${NC}"
echo -e "  • Application: $DOCKER_CONTAINER_NAME"
echo -e "  • Port: 8000"
echo -e "  • Cron job: Every 3 hours"
echo -e "  • Logs: $CRON_LOG_FILE"
echo -e "  • Health check: http://localhost:8000/health"

# Display useful commands
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo -e "  • View logs: docker logs $DOCKER_CONTAINER_NAME"
echo -e "  • Stop app: docker stop $DOCKER_CONTAINER_NAME"
echo -e "  • Start app: docker start $DOCKER_CONTAINER_NAME"
echo -e "  • View cron logs: tail -f $CRON_LOG_FILE"
echo -e "  • Check cron jobs: crontab -l"
echo -e "  • Manual cleanup: docker exec $DOCKER_CONTAINER_NAME python cleanup_old_reports.py"

print_status "Deployment script completed!"
