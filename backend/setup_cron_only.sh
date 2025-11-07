#!/bin/bash

# Cron Setup Script for Feed Formulation Backend
# Use this script if you already have the Docker container running

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration - Update these for your setup
APP_DIR="/home/jenkins/feed-formulation-be"  # Production path
DOCKER_CONTAINER_NAME="feed-formulation-be"  # Update container name
LOG_DIR="$APP_DIR/logs"
CRON_LOG_FILE="$LOG_DIR/cleanup.log"

echo -e "${BLUE}🔧 Setting up Cron Job for Report Cleanup${NC}"

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

# Check if Docker container is running
print_info "Checking if Docker container is running..."
if ! docker ps --format 'table {{.Names}}' | grep -q "$DOCKER_CONTAINER_NAME"; then
    print_error "Docker container '$DOCKER_CONTAINER_NAME' is not running."
    print_info "Please start your Docker container first, then run this script."
    exit 1
fi

print_status "Docker container is running"

# Create log directory if it doesn't exist
print_info "Creating log directory..."
mkdir -p "$LOG_DIR"
print_status "Log directory created"

# Create the cron job entry
CRON_JOB="0 */3 * * * cd $APP_DIR && docker exec $DOCKER_CONTAINER_NAME python cleanup_old_reports.py >> $CRON_LOG_FILE 2>&1"

# Check if cron job already exists
print_info "Checking for existing cron job..."
if crontab -l 2>/dev/null | grep -q "cleanup_old_reports.py"; then
    print_warning "Cron job already exists. Removing old entry..."
    # Remove existing cron job
    crontab -l 2>/dev/null | grep -v "cleanup_old_reports.py" | crontab -
    print_status "Old cron job removed"
fi

# Add new cron job
print_info "Adding new cron job..."
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

# Set up log rotation (optional)
print_info "Setting up log rotation..."
if [ -w /etc/logrotate.d/ ]; then
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
else
    print_warning "Cannot write to /etc/logrotate.d/. Log rotation not configured."
    print_info "You may need to run this script with sudo for log rotation setup."
fi

# Final status
echo -e "${GREEN}🎉 Cron setup completed successfully!${NC}"
echo -e "${BLUE}📋 Setup Summary:${NC}"
echo -e "  • Container: $DOCKER_CONTAINER_NAME"
echo -e "  • Cron job: Every 3 hours"
echo -e "  • Logs: $CRON_LOG_FILE"

# Display useful commands
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo -e "  • View cron logs: tail -f $CRON_LOG_FILE"
echo -e "  • Check cron jobs: crontab -l"
echo -e "  • Manual cleanup: docker exec $DOCKER_CONTAINER_NAME python cleanup_old_reports.py"
echo -e "  • Remove cron job: crontab -e (then delete the line)"

print_status "Cron setup script completed!"
