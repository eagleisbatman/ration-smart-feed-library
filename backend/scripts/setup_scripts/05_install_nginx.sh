#!/bin/bash
# Nginx Installation and Configuration Script
# This script installs and configures Nginx web server

set -e  # Exit on any error

echo "🌐 Starting Nginx installation and configuration..."

# Update package index
echo "📦 Updating package index..."
sudo apt update

# Install Nginx
echo "🌐 Installing Nginx..."
sudo apt install -y nginx

# Start and enable Nginx service
echo "🚀 Starting Nginx service..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Get Nginx version
NGINX_VERSION=$(nginx -v 2>&1 | grep -oP '\d+\.\d+\.\d+')
echo "📊 Nginx version: $NGINX_VERSION"

# Create application directory structure
echo "📁 Creating application directory structure..."
sudo mkdir -p /var/www/feed-formulation
sudo mkdir -p /var/log/nginx/feed-formulation
sudo chown -R ubuntu:ubuntu /var/www/feed-formulation
sudo chown -R ubuntu:ubuntu /var/log/nginx/feed-formulation

# Create Nginx configuration for the application
echo "⚙️  Creating Nginx configuration..."
sudo tee /etc/nginx/sites-available/feed-formulation > /dev/null <<EOF
# Feed Formulation Backend - Nginx Configuration
server {
    listen 80;
    server_name _;  # Will be updated when domain is configured
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Logging
    access_log /var/log/nginx/feed-formulation/access.log;
    error_log /var/log/nginx/feed-formulation/error.log;
    
    # Client settings
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Proxy to FastAPI application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # Static files (if any)
    location /static/ {
        alias /var/www/feed-formulation/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Deny access to hidden files
    location ~ /\. {
        deny all;
    }
}
EOF

# Create SSL configuration template (for later use)
echo "🔒 Creating SSL configuration template..."
sudo tee /etc/nginx/sites-available/feed-formulation-ssl > /dev/null <<EOF
# Feed Formulation Backend - SSL Configuration Template
# This will be configured when SSL certificate is obtained

server {
    listen 80;
    server_name DOMAIN_NAME;  # Replace with actual domain
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name DOMAIN_NAME;  # Replace with actual domain
    
    # SSL Configuration (will be updated by Certbot)
    ssl_certificate /etc/letsencrypt/live/DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_NAME/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Logging
    access_log /var/log/nginx/feed-formulation/access.log;
    error_log /var/log/nginx/feed-formulation/error.log;
    
    # Client settings
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;
    
    # Proxy to FastAPI application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # Static files (if any)
    location /static/ {
        alias /var/www/feed-formulation/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Deny access to hidden files
    location ~ /\. {
        deny all;
    }
}
EOF

# Enable the site
echo "🔗 Enabling Nginx site..."
sudo ln -sf /etc/nginx/sites-available/feed-formulation /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

# Reload Nginx to apply configuration
echo "🔄 Reloading Nginx..."
sudo systemctl reload nginx

# Set up Nginx log rotation
echo "📝 Setting up Nginx log rotation..."
sudo tee /etc/logrotate.d/nginx > /dev/null <<EOF
/var/log/nginx/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 640 nginx adm
    sharedscripts
    postrotate
        if [ -f /var/run/nginx.pid ]; then
            kill -USR1 \$(cat /var/run/nginx.pid)
        fi
    endscript
}
EOF

# Create a simple health check page
echo "🏥 Creating health check page..."
sudo tee /var/www/feed-formulation/index.html > /dev/null <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Feed Formulation Backend - Health Check</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        .status { color: green; font-size: 24px; }
        .info { color: #666; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>Feed Formulation Backend</h1>
    <div class="status">✅ Nginx is running</div>
    <div class="info">
        <p>Server is ready for application deployment</p>
        <p>API Documentation: <a href="/docs">/docs</a></p>
    </div>
</body>
</html>
EOF

# Set proper permissions
sudo chown ubuntu:ubuntu /var/www/feed-formulation/index.html

# Display Nginx information
echo "📊 Nginx Information:"
echo "Status: $(sudo systemctl is-active nginx)"
echo "Version: $NGINX_VERSION"
echo "Configuration: /etc/nginx/sites-available/feed-formulation"
echo "Logs: /var/log/nginx/feed-formulation/"

# Test Nginx response
echo "🧪 Testing Nginx response..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost/health | grep -q "200"; then
    echo "✅ Nginx health check successful"
else
    echo "⚠️  Nginx health check failed - this is expected until the application is deployed"
fi

echo "✅ Nginx installation and configuration completed successfully!"
echo ""
echo "📋 Nginx is now configured to:"
echo "   - Listen on port 80"
echo "   - Proxy requests to FastAPI on port 8000"
echo "   - Serve static files from /var/www/feed-formulation/static/"
echo "   - Log to /var/log/nginx/feed-formulation/"
echo ""
echo "🔒 SSL configuration template is ready for when you set up HTTPS"
echo "🌐 You can access the server at: http://$(curl -s ifconfig.me)/"
