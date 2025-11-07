#!/bin/bash
# Health Check and Monitoring Script
# This script performs comprehensive health checks on the deployed system

set -e  # Exit on any error

echo "🏥 Starting comprehensive health check..."

# Get server information
echo "📊 Server Information:"
echo "   Hostname: $(hostname)"
echo "   OS: $(lsb_release -d | cut -f2)"
echo "   Kernel: $(uname -r)"
echo "   Uptime: $(uptime -p)"
echo "   Load: $(uptime | awk -F'load average:' '{print $2}')"
echo "   Memory: $(free -h | grep '^Mem:' | awk '{print $3 "/" $2 " (" $5 " used)"}')"
echo "   Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"

# Check system services
echo ""
echo "🔧 System Services Status:"
services=("docker" "postgresql" "nginx" "ufw")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo "   ✅ $service: Running"
    else
        echo "   ❌ $service: Not running"
    fi
done

# Check Docker
echo ""
echo "🐳 Docker Status:"
if command -v docker &> /dev/null; then
    echo "   ✅ Docker is installed"
    echo "   Version: $(docker --version | cut -d' ' -f3 | cut -d',' -f1)"
    
    # Check Docker daemon
    if docker info &> /dev/null; then
        echo "   ✅ Docker daemon is running"
        
        # Check application container
        if docker ps | grep -q "feed-formulation-be"; then
            echo "   ✅ Application container is running"
            container_status=$(docker inspect --format='{{.State.Status}}' feed-formulation-be)
            echo "   Container status: $container_status"
            
            # Check container health
            if [ "$container_status" = "running" ]; then
                echo "   ✅ Container is healthy"
            else
                echo "   ❌ Container is not healthy"
            fi
        else
            echo "   ❌ Application container is not running"
        fi
    else
        echo "   ❌ Docker daemon is not running"
    fi
else
    echo "   ❌ Docker is not installed"
fi

# Check PostgreSQL
echo ""
echo "🐘 PostgreSQL Status:"
if command -v psql &> /dev/null; then
    echo "   ✅ PostgreSQL is installed"
    
    # Check if PostgreSQL is running
    if systemctl is-active --quiet postgresql; then
        echo "   ✅ PostgreSQL service is running"
        
        # Test database connection
        if sudo -u postgres psql -c "SELECT version();" &> /dev/null; then
            echo "   ✅ Database connection is working"
            
            # Check if application database exists
            if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw feed_formulation; then
                echo "   ✅ Application database exists"
            else
                echo "   ⚠️  Application database does not exist (run migrations when ready)"
            fi
        else
            echo "   ❌ Database connection failed"
        fi
    else
        echo "   ❌ PostgreSQL service is not running"
    fi
else
    echo "   ❌ PostgreSQL is not installed"
fi

# Check Nginx
echo ""
echo "🌐 Nginx Status:"
if command -v nginx &> /dev/null; then
    echo "   ✅ Nginx is installed"
    echo "   Version: $(nginx -v 2>&1 | cut -d' ' -f3)"
    
    # Check if Nginx is running
    if systemctl is-active --quiet nginx; then
        echo "   ✅ Nginx service is running"
        
        # Test Nginx configuration
        if nginx -t &> /dev/null; then
            echo "   ✅ Nginx configuration is valid"
        else
            echo "   ❌ Nginx configuration has errors"
        fi
        
        # Check if site is enabled
        if [ -L "/etc/nginx/sites-enabled/feed-formulation" ] || [ -L "/etc/nginx/sites-enabled/feed-formulation-ssl" ]; then
            echo "   ✅ Application site is enabled"
        else
            echo "   ❌ Application site is not enabled"
        fi
    else
        echo "   ❌ Nginx service is not running"
    fi
else
    echo "   ❌ Nginx is not installed"
fi

# Check Firewall
echo ""
echo "🔥 Firewall Status:"
if command -v ufw &> /dev/null; then
    echo "   ✅ UFW is installed"
    
    # Check firewall status
    ufw_status=$(ufw status | head -1)
    echo "   Status: $ufw_status"
    
    if echo "$ufw_status" | grep -q "active"; then
        echo "   ✅ Firewall is active"
        
        # Check important ports
        if ufw status | grep -q "22/tcp.*ALLOW"; then
            echo "   ✅ SSH access is allowed"
        else
            echo "   ❌ SSH access is not allowed"
        fi
        
        if ufw status | grep -q "80/tcp.*ALLOW"; then
            echo "   ✅ HTTP access is allowed"
        else
            echo "   ❌ HTTP access is not allowed"
        fi
        
        if ufw status | grep -q "443/tcp.*ALLOW"; then
            echo "   ✅ HTTPS access is allowed"
        else
            echo "   ❌ HTTPS access is not allowed"
        fi
    else
        echo "   ❌ Firewall is not active"
    fi
else
    echo "   ❌ UFW is not installed"
fi

# Check Application Endpoints
echo ""
echo "🚀 Application Endpoints:"
server_ip=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")

# Test direct application access
if curl -s --connect-timeout 5 "http://localhost:8000/health" &> /dev/null; then
    echo "   ✅ Direct application access (port 8000) is working"
else
    echo "   ❌ Direct application access (port 8000) is not working"
fi

# Test Nginx proxy
if curl -s --connect-timeout 5 "http://localhost/health" &> /dev/null; then
    echo "   ✅ Nginx proxy access is working"
else
    echo "   ❌ Nginx proxy access is not working"
fi

# Test API documentation
if curl -s --connect-timeout 5 "http://localhost:8000/docs" &> /dev/null; then
    echo "   ✅ API documentation is accessible"
else
    echo "   ❌ API documentation is not accessible"
fi

# Test external access
echo ""
echo "🌐 External Access Test:"
if curl -s --connect-timeout 10 "http://$server_ip:8000/health" &> /dev/null; then
    echo "   ✅ External access to application is working"
    echo "   Application URL: http://$server_ip:8000"
    echo "   API Docs URL: http://$server_ip:8000/docs"
else
    echo "   ❌ External access to application is not working"
fi

# Check SSL (if configured)
if [ -f "/etc/letsencrypt/live" ]; then
    echo ""
    echo "🔒 SSL Certificate Status:"
    if command -v certbot &> /dev/null; then
        echo "   ✅ Certbot is installed"
        
        # Check certificate status
        cert_info=$(sudo certbot certificates 2>/dev/null | grep -A 5 "Certificate Name" || echo "No certificates found")
        if echo "$cert_info" | grep -q "Certificate Name"; then
            echo "   ✅ SSL certificates are configured"
            echo "   Certificate info:"
            echo "$cert_info" | sed 's/^/     /'
        else
            echo "   ⚠️  No SSL certificates found"
        fi
    else
        echo "   ❌ Certbot is not installed"
    fi
fi

# Check Log Files
echo ""
echo "📝 Log Files Status:"
log_dirs=("/var/log/nginx/feed-formulation" "/var/log/postgresql" "/var/log/feed-formulation")
for log_dir in "${log_dirs[@]}"; do
    if [ -d "$log_dir" ]; then
        echo "   ✅ $log_dir exists"
        log_count=$(find "$log_dir" -name "*.log" 2>/dev/null | wc -l)
        echo "     Log files: $log_count"
    else
        echo "   ⚠️  $log_dir does not exist"
    fi
done

# Check Disk Space
echo ""
echo "💾 Disk Space Check:"
df -h | grep -E '^/dev/' | while read line; do
    usage=$(echo "$line" | awk '{print $5}' | sed 's/%//')
    partition=$(echo "$line" | awk '{print $6}')
    size=$(echo "$line" | awk '{print $2}')
    used=$(echo "$line" | awk '{print $3}')
    
    if [ "$usage" -ge 90 ]; then
        echo "   ❌ $partition: $used/$size ($usage% used) - CRITICAL"
    elif [ "$usage" -ge 80 ]; then
        echo "   ⚠️  $partition: $used/$size ($usage% used) - WARNING"
    else
        echo "   ✅ $partition: $used/$size ($usage% used) - OK"
    fi
done

# Check Memory Usage
echo ""
echo "🧠 Memory Usage Check:"
memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
if (( $(echo "$memory_usage > 90" | bc -l) )); then
    echo "   ❌ Memory usage: ${memory_usage}% - CRITICAL"
elif (( $(echo "$memory_usage > 80" | bc -l) )); then
    echo "   ⚠️  Memory usage: ${memory_usage}% - WARNING"
else
    echo "   ✅ Memory usage: ${memory_usage}% - OK"
fi

# Check Load Average
echo ""
echo "⚡ Load Average Check:"
load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
cpu_cores=$(nproc)
if (( $(echo "$load_avg > $cpu_cores * 2" | bc -l) )); then
    echo "   ❌ Load average: $load_avg (CPUs: $cpu_cores) - HIGH LOAD"
elif (( $(echo "$load_avg > $cpu_cores" | bc -l) )); then
    echo "   ⚠️  Load average: $load_avg (CPUs: $cpu_cores) - MODERATE LOAD"
else
    echo "   ✅ Load average: $load_avg (CPUs: $cpu_cores) - NORMAL"
fi

# Final Health Summary
echo ""
echo "📋 Health Check Summary:"
echo "========================"

# Count issues
issues=0
warnings=0

# Check critical services
if ! systemctl is-active --quiet docker; then
    echo "❌ CRITICAL: Docker is not running"
    ((issues++))
fi

if ! systemctl is-active --quiet postgresql; then
    echo "❌ CRITICAL: PostgreSQL is not running"
    ((issues++))
fi

if ! systemctl is-active --quiet nginx; then
    echo "❌ CRITICAL: Nginx is not running"
    ((issues++))
fi

if ! docker ps | grep -q "feed-formulation-be"; then
    echo "❌ CRITICAL: Application container is not running"
    ((issues++))
fi

# Check application connectivity
if ! curl -s --connect-timeout 5 "http://localhost:8000/health" &> /dev/null; then
    echo "❌ CRITICAL: Application is not responding"
    ((issues++))
fi

# Check disk space
disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$disk_usage" -ge 90 ]; then
    echo "❌ CRITICAL: Disk space is critically low ($disk_usage%)"
    ((issues++))
elif [ "$disk_usage" -ge 80 ]; then
    echo "⚠️  WARNING: Disk space is getting low ($disk_usage%)"
    ((warnings++))
fi

# Final status
if [ $issues -eq 0 ] && [ $warnings -eq 0 ]; then
    echo "🎉 ALL SYSTEMS HEALTHY!"
    echo "✅ Your Feed Formulation Backend is running perfectly"
    exit 0
elif [ $issues -eq 0 ]; then
    echo "⚠️  SYSTEM HEALTHY WITH WARNINGS"
    echo "✅ Core systems are working, but there are $warnings warning(s)"
    exit 0
else
    echo "❌ SYSTEM HAS ISSUES"
    echo "🚨 There are $issues critical issue(s) that need attention"
    exit 1
fi
