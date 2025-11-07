#!/bin/bash
# Complete Server Cleanup Script
# This script removes all components installed by the setup scripts
# WARNING: This will completely clean the server - use with caution!

set -e  # Exit on any error

echo "🧹 Starting complete server cleanup..."
echo "⚠️  WARNING: This will remove ALL installed components!"
echo "⚠️  This includes: Docker, PostgreSQL, Nginx, applications, and data!"
echo ""

# Confirmation prompt
read -p "Are you sure you want to proceed with complete cleanup? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Cleanup cancelled by user"
    exit 1
fi

echo "🚀 Proceeding with complete cleanup..."

# =====================================================
# 1. STOP ALL SERVICES
# =====================================================
echo "🛑 Stopping all services..."

# Stop Docker containers
echo "   Stopping Docker containers..."
docker stop $(docker ps -aq) 2>/dev/null || echo "   No Docker containers to stop"

# Stop system services
echo "   Stopping system services..."
sudo systemctl stop nginx 2>/dev/null || echo "   Nginx not running"
sudo systemctl stop postgresql 2>/dev/null || echo "   PostgreSQL not running"
sudo systemctl stop docker 2>/dev/null || echo "   Docker not running"
sudo systemctl stop fail2ban 2>/dev/null || echo "   Fail2ban not running"

# =====================================================
# 2. REMOVE DOCKER CONTAINERS AND IMAGES
# =====================================================
echo "🐳 Removing Docker components..."

# Remove all containers
echo "   Removing all Docker containers..."
docker rm -f $(docker ps -aq) 2>/dev/null || echo "   No containers to remove"

# Remove all images
echo "   Removing all Docker images..."
docker rmi -f $(docker images -aq) 2>/dev/null || echo "   No images to remove"

# Remove all volumes
echo "   Removing all Docker volumes..."
docker volume rm $(docker volume ls -q) 2>/dev/null || echo "   No volumes to remove"

# Remove all networks
echo "   Removing all Docker networks..."
docker network rm $(docker network ls -q) 2>/dev/null || echo "   No networks to remove"

# =====================================================
# 3. REMOVE APPLICATION DATA
# =====================================================
echo "📁 Removing application data..."

# Remove application directory
echo "   Removing application directory..."
sudo rm -rf /home/ubuntu/feed-formulation-be 2>/dev/null || echo "   Application directory not found"

# Remove application logs
echo "   Removing application logs..."
sudo rm -rf /var/log/feed-formulation 2>/dev/null || echo "   Application logs not found"

# Remove result HTML files
echo "   Removing result files..."
sudo rm -rf /home/ubuntu/result_html 2>/dev/null || echo "   Result files not found"

# Remove diet reports
echo "   Removing diet reports..."
sudo rm -rf /home/ubuntu/diet_reports 2>/dev/null || echo "   Diet reports not found"

# =====================================================
# 4. REMOVE DATABASE DATA
# =====================================================
echo "🗄️  Removing database data..."

# Drop application database
echo "   Dropping application database..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS feed_formulation;" 2>/dev/null || echo "   Database not found"

# Drop application user
echo "   Dropping application user..."
sudo -u postgres psql -c "DROP USER IF EXISTS feed_user;" 2>/dev/null || echo "   User not found"

# Remove PostgreSQL data directory (optional - uncomment if you want to remove ALL PostgreSQL data)
# echo "   Removing PostgreSQL data directory..."
# sudo rm -rf /var/lib/postgresql 2>/dev/null || echo "   PostgreSQL data not found"

# =====================================================
# 5. REMOVE NGINX CONFIGURATION
# =====================================================
echo "🌐 Removing Nginx configuration..."

# Remove application configuration
echo "   Removing Nginx application configuration..."
sudo rm -f /etc/nginx/sites-available/feed-formulation 2>/dev/null || echo "   Nginx config not found"
sudo rm -f /etc/nginx/sites-enabled/feed-formulation 2>/dev/null || echo "   Nginx config not found"

# Remove SSL certificates
echo "   Removing SSL certificates..."
sudo rm -rf /etc/letsencrypt 2>/dev/null || echo "   SSL certificates not found"

# Remove Nginx logs
echo "   Removing Nginx logs..."
sudo rm -rf /var/log/nginx/feed-formulation 2>/dev/null || echo "   Nginx logs not found"

# =====================================================
# 6. REMOVE SYSTEM PACKAGES
# =====================================================
echo "📦 Removing installed packages..."

# Remove Docker
echo "   Removing Docker..."
sudo apt remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>/dev/null || echo "   Docker not installed"
sudo apt remove -y docker.io docker-compose 2>/dev/null || echo "   Docker.io not installed"

# Remove PostgreSQL
echo "   Removing PostgreSQL..."
sudo apt remove -y postgresql postgresql-contrib 2>/dev/null || echo "   PostgreSQL not installed"

# Remove Nginx
echo "   Removing Nginx..."
sudo apt remove -y nginx 2>/dev/null || echo "   Nginx not installed"

# Remove Certbot
echo "   Removing Certbot..."
sudo apt remove -y certbot python3-certbot-nginx 2>/dev/null || echo "   Certbot not installed"

# Remove other packages
echo "   Removing other packages..."
sudo apt remove -y fail2ban unattended-upgrades 2>/dev/null || echo "   Other packages not installed"

# =====================================================
# 7. REMOVE CONFIGURATION FILES
# =====================================================
echo "⚙️  Removing configuration files..."

# Remove Docker configuration
echo "   Removing Docker configuration..."
sudo rm -rf /etc/docker 2>/dev/null || echo "   Docker config not found"
sudo rm -rf /var/lib/docker 2>/dev/null || echo "   Docker data not found"

# Remove PostgreSQL configuration
echo "   Removing PostgreSQL configuration..."
sudo rm -rf /etc/postgresql 2>/dev/null || echo "   PostgreSQL config not found"

# Remove Nginx configuration
echo "   Removing Nginx configuration..."
sudo rm -rf /etc/nginx 2>/dev/null || echo "   Nginx config not found"

# Remove fail2ban configuration
echo "   Removing fail2ban configuration..."
sudo rm -rf /etc/fail2ban 2>/dev/null || echo "   Fail2ban config not found"

# Remove cron jobs
echo "   Removing cron jobs..."
sudo rm -f /etc/cron.d/system-monitor 2>/dev/null || echo "   Cron jobs not found"
sudo rm -f /etc/cron.d/feed-formulation 2>/dev/null || echo "   Cron jobs not found"

# Remove log rotation configuration
echo "   Removing log rotation configuration..."
sudo rm -f /etc/logrotate.d/feed-formulation 2>/dev/null || echo "   Log rotation config not found"

# =====================================================
# 8. REMOVE USER GROUPS AND PERMISSIONS
# =====================================================
echo "👤 Removing user groups and permissions..."

# Remove user from docker group
echo "   Removing user from docker group..."
sudo deluser ubuntu docker 2>/dev/null || echo "   User not in docker group"

# Remove docker group
echo "   Removing docker group..."
sudo groupdel docker 2>/dev/null || echo "   Docker group not found"

# =====================================================
# 9. RESET FIREWALL
# =====================================================
echo "🔥 Resetting firewall..."

# Reset UFW to default
echo "   Resetting UFW firewall..."
sudo ufw --force reset 2>/dev/null || echo "   UFW not configured"

# =====================================================
# 10. CLEAN UP SYSTEM
# =====================================================
echo "🧹 Cleaning up system..."

# Clean package cache
echo "   Cleaning package cache..."
sudo apt autoremove -y 2>/dev/null || echo "   No packages to remove"
sudo apt autoclean 2>/dev/null || echo "   Cache already clean"

# Clean temporary files
echo "   Cleaning temporary files..."
sudo rm -rf /tmp/* 2>/dev/null || echo "   Temp files already clean"

# Clean logs
echo "   Cleaning system logs..."
sudo truncate -s 0 /var/log/syslog 2>/dev/null || echo "   Syslog already clean"
sudo truncate -s 0 /var/log/auth.log 2>/dev/null || echo "   Auth log already clean"

# =====================================================
# 11. RESTORE SSH CONFIGURATION (OPTIONAL)
# =====================================================
echo "🔐 Restoring SSH configuration..."

# Restore original SSH configuration
echo "   Restoring SSH configuration..."
if [ -f /etc/ssh/sshd_config.backup ]; then
    sudo cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
    sudo systemctl restart ssh
    echo "   SSH configuration restored from backup"
else
    echo "   No SSH backup found, keeping current configuration"
fi

# =====================================================
# 12. FINAL CLEANUP
# =====================================================
echo "🎯 Final cleanup..."

# Remove setup scripts from /tmp
echo "   Removing setup scripts from /tmp..."
sudo rm -rf /tmp/01_connect_test.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/02_system_update.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/03_install_docker.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/04_install_postgresql.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/05_install_nginx.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/06_configure_firewall.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/07_setup_github.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/08_deploy_application.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/09_setup_ssl.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/10_health_check.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/11_create_database.sh 2>/dev/null || echo "   Setup scripts not found"
sudo rm -rf /tmp/11_create_database_schema.sql 2>/dev/null || echo "   Setup scripts not found"

# Remove management scripts
echo "   Removing management scripts..."
sudo rm -f /home/ubuntu/manage_app.sh 2>/dev/null || echo "   Management scripts not found"
sudo rm -f /home/ubuntu/monitor_app.sh 2>/dev/null || echo "   Management scripts not found"
sudo rm -f /home/ubuntu/monitor_ssl.sh 2>/dev/null || echo "   Management scripts not found"

# =====================================================
# 13. VERIFICATION
# =====================================================
echo "🔍 Verifying cleanup..."

# Check if services are stopped
echo "   Checking service status..."
services=("docker" "postgresql" "nginx" "fail2ban")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo "   ⚠️  $service is still running"
    else
        echo "   ✅ $service is stopped"
    fi
done

# Check if packages are removed
echo "   Checking package removal..."
packages=("docker" "postgresql" "nginx" "certbot")
for package in "${packages[@]}"; do
    if dpkg -l | grep -q "^ii.*$package"; then
        echo "   ⚠️  $package is still installed"
    else
        echo "   ✅ $package is removed"
    fi
done

# Check disk space
echo "   Checking disk space..."
df -h / | tail -1 | awk '{print "   Disk usage: " $3 "/" $2 " (" $5 " used)"}'

# =====================================================
# 14. COMPLETION
# =====================================================
echo ""
echo "✅ Server cleanup completed successfully!"
echo ""
echo "📋 Cleanup Summary:"
echo "   🐳 Docker: Removed containers, images, volumes, networks"
echo "   🗄️  PostgreSQL: Removed database, user, and data"
echo "   🌐 Nginx: Removed configuration and SSL certificates"
echo "   🔥 Firewall: Reset to default state"
echo "   📦 Packages: Removed Docker, PostgreSQL, Nginx, Certbot"
echo "   📁 Data: Removed application directories and logs"
echo "   ⚙️  Configuration: Removed all configuration files"
echo "   👤 Users: Removed from docker group"
echo "   🧹 System: Cleaned temporary files and logs"
echo ""
echo "🚀 Server is now in a clean state!"
echo "📝 You can now run the setup scripts again for a fresh installation."
echo ""
echo "⚠️  Note: Some system packages may still be present."
echo "   Run 'sudo apt autoremove -y' to remove unused packages."
echo "   Run 'sudo apt autoclean' to clean package cache."
echo ""
echo "🔄 To start fresh setup, run:"
echo "   bash 01_connect_test.sh"
echo "   bash 02_system_update.sh"
echo "   # ... and so on"
