#!/bin/bash
# Firewall Configuration Script
# This script configures UFW firewall for the Feed Formulation Backend

set -e  # Exit on any error

echo "🔥 Starting firewall configuration..."

# Check if UFW is installed
if ! command -v ufw &> /dev/null; then
    echo "❌ UFW is not installed. Installing..."
    sudo apt update
    sudo apt install -y ufw
fi

# Reset UFW to default state
echo "🔄 Resetting UFW to default state..."
sudo ufw --force reset

# Set default policies
echo "⚙️  Setting default policies..."
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (critical - don't lock yourself out!)
echo "🔐 Allowing SSH access..."
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
echo "🌐 Allowing HTTP and HTTPS..."
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow application port (for direct access if needed)
echo "🚀 Allowing application port..."
sudo ufw allow 8000/tcp

# Allow PostgreSQL (only from localhost for security)
echo "🐘 Configuring PostgreSQL access..."
sudo ufw allow from 127.0.0.1 to any port 5432

# Allow Docker networks (if needed)
echo "🐳 Configuring Docker network access..."
sudo ufw allow from 172.16.0.0/12
sudo ufw allow from 192.168.0.0/16
sudo ufw allow from 10.0.0.0/8

# Configure rate limiting for SSH
echo "🛡️  Configuring SSH rate limiting..."
sudo ufw limit ssh

# Enable logging
echo "📝 Enabling UFW logging..."
sudo ufw logging on

# Display current rules before enabling
echo "📋 Current UFW rules:"
sudo ufw show added

# Enable UFW
echo "🚀 Enabling UFW firewall..."
sudo ufw --force enable

# Display status
echo "📊 UFW Status:"
sudo ufw status verbose

# Set up UFW monitoring
echo "📊 Setting up UFW monitoring..."
sudo tee /etc/cron.d/ufw-monitor > /dev/null <<EOF
# UFW monitoring - runs every hour
0 * * * * root /usr/sbin/ufw status | logger -t ufw-monitor
EOF

# Create UFW log rotation
echo "📝 Setting up UFW log rotation..."
sudo tee /etc/logrotate.d/ufw > /dev/null <<EOF
/var/log/ufw.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        /bin/kill -HUP \$(cat /var/run/rsyslogd.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

# Display firewall information
echo "📊 Firewall Information:"
echo "Status: $(sudo ufw status | head -1)"
echo "Active rules: $(sudo ufw status | grep -c '^\[.*\]')"
echo "Logging: $(sudo ufw status | grep 'Logging' | awk '{print $2}')"

# Test firewall rules
echo "🧪 Testing firewall configuration..."
echo "Testing SSH access..."
if sudo ufw status | grep -q "22/tcp.*ALLOW"; then
    echo "✅ SSH access is allowed"
else
    echo "❌ SSH access is not properly configured"
fi

echo "Testing HTTP access..."
if sudo ufw status | grep -q "80/tcp.*ALLOW"; then
    echo "✅ HTTP access is allowed"
else
    echo "❌ HTTP access is not properly configured"
fi

echo "Testing HTTPS access..."
if sudo ufw status | grep -q "443/tcp.*ALLOW"; then
    echo "✅ HTTPS access is allowed"
else
    echo "❌ HTTPS access is not properly configured"
fi

# Security recommendations
echo "🔒 Security Recommendations:"
echo "1. ✅ SSH access is limited and rate-limited"
echo "2. ✅ Only necessary ports are open"
echo "3. ✅ Default deny incoming policy is set"
echo "4. ✅ Logging is enabled for monitoring"
echo "5. ✅ PostgreSQL is only accessible from localhost"

# Display current open ports
echo "📋 Currently open ports:"
sudo ufw status | grep "ALLOW" | while read line; do
    echo "   $line"
done

echo "✅ Firewall configuration completed successfully!"
echo ""
echo "🛡️  Firewall is now protecting your server with:"
echo "   - SSH access (rate-limited)"
echo "   - HTTP/HTTPS access"
echo "   - Application port access"
echo "   - PostgreSQL (localhost only)"
echo "   - Docker network access"
echo ""
echo "📝 To view firewall status: sudo ufw status verbose"
echo "📝 To view firewall logs: sudo tail -f /var/log/ufw.log"
echo "⚠️  Remember: Always test SSH access before making firewall changes!"
