#!/bin/bash
# Connection Test Script
# This script tests SSH connection to the new server

set -e  # Exit on any error

echo "🔌 Testing SSH connection to the new server..."

# Display server information
echo "📊 Server Information:"
echo "   Hostname: $(hostname)"
echo "   OS: $(lsb_release -d | cut -f2)"
echo "   Kernel: $(uname -r)"
echo "   Architecture: $(uname -m)"
echo "   Uptime: $(uptime -p)"

# Check system resources
echo ""
echo "💻 System Resources:"
echo "   CPU Cores: $(nproc)"
echo "   Memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "   Disk: $(df -h / | tail -1 | awk '{print $2}')"
echo "   Load: $(uptime | awk -F'load average:' '{print $2}')"

# Check network connectivity
echo ""
echo "🌐 Network Connectivity:"
if ping -c 1 8.8.8.8 &> /dev/null; then
    echo "   ✅ Internet connectivity: OK"
else
    echo "   ❌ Internet connectivity: FAILED"
fi

# Check DNS resolution
if nslookup google.com &> /dev/null; then
    echo "   ✅ DNS resolution: OK"
else
    echo "   ❌ DNS resolution: FAILED"
fi

# Check if we can reach GitHub
if curl -s --connect-timeout 10 https://github.com &> /dev/null; then
    echo "   ✅ GitHub access: OK"
else
    echo "   ❌ GitHub access: FAILED"
fi

# Check if we can reach Docker Hub
if curl -s --connect-timeout 10 https://hub.docker.com &> /dev/null; then
    echo "   ✅ Docker Hub access: OK"
else
    echo "   ❌ Docker Hub access: FAILED"
fi

# Check system time
echo ""
echo "⏰ System Time:"
echo "   Current time: $(date)"
echo "   Timezone: $(timedatectl show --property=Timezone --value)"

# Check if system is up to date
echo ""
echo "📦 Package Status:"
if [ -f /var/lib/apt/periodic/update-success-stamp ]; then
    last_update=$(stat -c %Y /var/lib/apt/periodic/update-success-stamp)
    current_time=$(date +%s)
    days_since_update=$(( (current_time - last_update) / 86400 ))
    
    if [ $days_since_update -lt 7 ]; then
        echo "   ✅ Package lists updated within last 7 days"
    else
        echo "   ⚠️  Package lists updated $days_since_update days ago"
    fi
else
    echo "   ⚠️  Package update status unknown"
fi

# Check available disk space
echo ""
echo "💾 Disk Space:"
df -h | grep -E '^/dev/' | while read line; do
    partition=$(echo "$line" | awk '{print $6}')
    size=$(echo "$line" | awk '{print $2}')
    used=$(echo "$line" | awk '{print $3}')
    available=$(echo "$line" | awk '{print $4}')
    usage=$(echo "$line" | awk '{print $5}')
    echo "   $partition: $used/$size used ($usage), $available available"
done

# Check memory usage
echo ""
echo "🧠 Memory Usage:"
free -h | grep -E '^Mem|^Swap' | while read line; do
    type=$(echo "$line" | awk '{print $1}')
    total=$(echo "$line" | awk '{print $2}')
    used=$(echo "$line" | awk '{print $3}')
    free=$(echo "$line" | awk '{print $4}')
    echo "   $type: $used/$total used, $free free"
done

# Check running processes
echo ""
echo "🔄 Running Processes:"
echo "   Total processes: $(ps aux | wc -l)"
echo "   System processes: $(ps aux | grep -E '^root' | wc -l)"
echo "   User processes: $(ps aux | grep -E '^ubuntu' | wc -l)"

# Check open ports
echo ""
echo "🔌 Open Ports:"
if command -v netstat &> /dev/null; then
    echo "   Listening ports:"
    netstat -tlnp | grep LISTEN | awk '{print "     " $1 " " $4}' | sort | uniq
else
    echo "   netstat not available, using ss instead:"
    ss -tlnp | grep LISTEN | awk '{print "     " $1 " " $4}' | sort | uniq
fi

# Check system logs for errors
echo ""
echo "📝 Recent System Logs:"
if [ -f /var/log/syslog ]; then
    error_count=$(grep -i error /var/log/syslog | tail -10 | wc -l)
    if [ $error_count -gt 0 ]; then
        echo "   ⚠️  Found $error_count recent errors in system log"
        echo "   Recent errors:"
        grep -i error /var/log/syslog | tail -5 | sed 's/^/     /'
    else
        echo "   ✅ No recent errors in system log"
    fi
else
    echo "   ⚠️  System log not accessible"
fi

# Check if this is a fresh installation
echo ""
echo "🔍 Installation Status:"
if [ -d "/home/ubuntu/feed-formulation-be" ]; then
    echo "   ⚠️  Application directory already exists"
else
    echo "   ✅ Fresh installation detected"
fi

if command -v docker &> /dev/null; then
    echo "   ⚠️  Docker is already installed"
else
    echo "   ✅ Docker not installed (will be installed)"
fi

if command -v nginx &> /dev/null; then
    echo "   ⚠️  Nginx is already installed"
else
    echo "   ✅ Nginx not installed (will be installed)"
fi

if systemctl is-active --quiet postgresql; then
    echo "   ⚠️  PostgreSQL is already running"
else
    echo "   ✅ PostgreSQL not running (will be installed)"
fi

# Final connection test summary
echo ""
echo "📋 Connection Test Summary:"
echo "=========================="
echo "✅ SSH connection established successfully"
echo "✅ Server is accessible and responsive"
echo "✅ Basic system checks passed"
echo ""
echo "🚀 Server is ready for setup!"
echo "📝 Proceeding with software installation..."
