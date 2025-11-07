#!/bin/bash
# System Update and Security Hardening Script
# This script updates Ubuntu and configures basic security settings

set -e  # Exit on any error

echo "🔄 Starting system update and security configuration..."

# Update package lists
echo "📦 Updating package lists..."
sudo apt update

# Upgrade all packages
echo "⬆️  Upgrading all packages..."
sudo apt upgrade -y

# Install essential tools
echo "🛠️  Installing essential tools..."
sudo apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    unzip \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    unattended-upgrades

# Configure automatic security updates
echo "🔒 Configuring automatic security updates..."
sudo dpkg-reconfigure -plow unattended-upgrades

# Set up fail2ban for SSH protection
echo "🛡️  Configuring fail2ban..."
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Create fail2ban jail for SSH
sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
EOF

# Restart fail2ban
sudo systemctl restart fail2ban

# Configure SSH security (basic hardening)
echo "🔐 Configuring SSH security..."
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Update SSH configuration for better security
sudo tee -a /etc/ssh/sshd_config > /dev/null <<EOF

# Security enhancements
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

# Restart SSH service
sudo systemctl restart ssh

# Set up log rotation for better log management
echo "📝 Configuring log rotation..."
sudo tee /etc/logrotate.d/feed-formulation > /dev/null <<EOF
/var/log/feed-formulation/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# Create application log directory
sudo mkdir -p /var/log/feed-formulation
sudo chown ubuntu:ubuntu /var/log/feed-formulation

# Set up system monitoring
echo "📊 Setting up basic system monitoring..."
sudo tee /etc/cron.d/system-monitor > /dev/null <<EOF
# System monitoring - runs every 5 minutes
*/5 * * * * root /usr/bin/df -h | grep -E '^/dev/' | awk '{print \$5 " " \$6}' | while read output; do
    usep=\$(echo \$output | awk '{print \$1}' | sed 's/%//')
    partition=\$(echo \$output | awk '{print \$2}')
    if [ \$usep -ge 90 ]; then
        echo "Disk space warning: \$partition is \$usep% full" | logger -t disk-monitor
    fi
done
EOF

# Clean up
echo "🧹 Cleaning up..."
sudo apt autoremove -y
sudo apt autoclean

# Display system information
echo "📊 System Information:"
echo "OS: $(lsb_release -d | cut -f2)"
echo "Kernel: $(uname -r)"
echo "Architecture: $(uname -m)"
echo "Uptime: $(uptime -p)"
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"

echo "✅ System update and security configuration completed successfully!"
echo "🔄 Please reboot the server to ensure all updates are applied:"
echo "   sudo reboot"
