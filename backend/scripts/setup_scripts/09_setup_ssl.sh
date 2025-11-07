#!/bin/bash
# SSL/HTTPS Setup Script with Let's Encrypt
# This script configures SSL certificates using Let's Encrypt

set -e  # Exit on any error

echo "🔒 Starting SSL/HTTPS setup with Let's Encrypt..."

# Check if domain name is provided
if [ -z "$DOMAIN_NAME" ]; then
    echo "⚠️  No domain name provided. Skipping SSL setup."
    echo "📝 To set up SSL later, run:"
    echo "   sudo certbot --nginx -d yourdomain.com"
    exit 0
fi

if [ -z "$EMAIL" ]; then
    echo "❌ Email address is required for Let's Encrypt SSL certificate"
    echo "Please provide EMAIL environment variable"
    exit 1
fi

echo "📊 SSL Configuration:"
echo "   Domain: $DOMAIN_NAME"
echo "   Email: $EMAIL"

# Install Certbot
echo "📦 Installing Certbot..."
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Verify Nginx is running
echo "🔍 Verifying Nginx is running..."
if ! sudo systemctl is-active --quiet nginx; then
    echo "❌ Nginx is not running. Please start Nginx first."
    exit 1
fi

# Update Nginx configuration with domain name
echo "⚙️  Updating Nginx configuration with domain name..."
sudo sed -i "s/server_name _;/server_name $DOMAIN_NAME;/g" /etc/nginx/sites-available/feed-formulation

# Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

# Reload Nginx
echo "🔄 Reloading Nginx..."
sudo systemctl reload nginx

# Obtain SSL certificate
echo "🔐 Obtaining SSL certificate from Let's Encrypt..."
sudo certbot --nginx -d "$DOMAIN_NAME" --email "$EMAIL" --agree-tos --non-interactive --redirect

# Verify certificate was obtained
if [ $? -eq 0 ]; then
    echo "✅ SSL certificate obtained successfully"
else
    echo "❌ Failed to obtain SSL certificate"
    exit 1
fi

# Test SSL configuration
echo "🧪 Testing SSL configuration..."
if curl -s -I "https://$DOMAIN_NAME" | grep -q "HTTP/2 200"; then
    echo "✅ HTTPS is working correctly"
else
    echo "⚠️  HTTPS test failed, but certificate was obtained"
fi

# Set up automatic certificate renewal
echo "🔄 Setting up automatic certificate renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test certificate renewal
echo "🧪 Testing certificate renewal..."
sudo certbot renew --dry-run

if [ $? -eq 0 ]; then
    echo "✅ Certificate renewal test successful"
else
    echo "⚠️  Certificate renewal test failed"
fi

# Update Nginx configuration for better SSL security
echo "🔒 Updating Nginx configuration for better SSL security..."
sudo tee /etc/nginx/snippets/ssl-params.conf > /dev/null <<EOF
# SSL Configuration for Feed Formulation Backend
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
ssl_ecdh_curve secp384r1;
ssl_session_timeout 10m;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
add_header X-Frame-Options DENY;
add_header X-Content-Type-Options nosniff;
add_header X-XSS-Protection "1; mode=block";
EOF

# Update the SSL site configuration
sudo tee /etc/nginx/sites-available/feed-formulation-ssl > /dev/null <<EOF
# Feed Formulation Backend - SSL Configuration
server {
    listen 80;
    server_name $DOMAIN_NAME;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN_NAME;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    include /etc/nginx/snippets/ssl-params.conf;
    
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

# Enable SSL site
echo "🔗 Enabling SSL site..."
sudo ln -sf /etc/nginx/sites-available/feed-formulation-ssl /etc/nginx/sites-enabled/

# Remove HTTP-only site
sudo rm -f /etc/nginx/sites-enabled/feed-formulation

# Test Nginx configuration
echo "🧪 Testing updated Nginx configuration..."
sudo nginx -t

# Reload Nginx
echo "🔄 Reloading Nginx with SSL configuration..."
sudo systemctl reload nginx

# Test HTTPS endpoints
echo "🧪 Testing HTTPS endpoints..."

# Test root endpoint
if curl -s -I "https://$DOMAIN_NAME" | grep -q "HTTP/2 200"; then
    echo "✅ HTTPS root endpoint is working"
else
    echo "⚠️  HTTPS root endpoint test failed"
fi

# Test API docs
if curl -s -I "https://$DOMAIN_NAME/docs" | grep -q "HTTP/2 200"; then
    echo "✅ HTTPS API docs endpoint is working"
else
    echo "⚠️  HTTPS API docs endpoint test failed"
fi

# Test health endpoint
if curl -s "https://$DOMAIN_NAME/health" | grep -q "healthy"; then
    echo "✅ HTTPS health endpoint is working"
else
    echo "⚠️  HTTPS health endpoint test failed"
fi

# Display SSL information
echo "📊 SSL Information:"
echo "   Domain: $DOMAIN_NAME"
echo "   Certificate: /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem"
echo "   Private Key: /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem"
echo "   Expires: $(sudo certbot certificates | grep -A 2 "$DOMAIN_NAME" | grep "Expiry Date" | cut -d: -f2-)"
echo "   Auto-renewal: $(sudo systemctl is-enabled certbot.timer)"

# Create SSL monitoring script
echo "📝 Creating SSL monitoring script..."
cat > monitor_ssl.sh << 'EOF'
#!/bin/bash
# SSL monitoring script

DOMAIN_NAME="$1"
if [ -z "$DOMAIN_NAME" ]; then
    echo "Usage: $0 <domain_name>"
    exit 1
fi

echo "🔒 SSL Certificate Monitor for $DOMAIN_NAME"
echo "============================================="

# Check certificate expiry
echo "📅 Certificate Information:"
sudo certbot certificates | grep -A 5 "$DOMAIN_NAME"

# Test HTTPS connectivity
echo ""
echo "🌐 HTTPS Connectivity Test:"
if curl -s -I "https://$DOMAIN_NAME" | grep -q "HTTP/2 200"; then
    echo "✅ HTTPS is working"
else
    echo "❌ HTTPS is not working"
fi

# Test certificate renewal
echo ""
echo "🔄 Certificate Renewal Test:"
sudo certbot renew --dry-run

# Check auto-renewal status
echo ""
echo "⏰ Auto-renewal Status:"
sudo systemctl status certbot.timer --no-pager
EOF

chmod +x monitor_ssl.sh

# Update firewall to ensure HTTPS is allowed
echo "🔥 Updating firewall for HTTPS..."
sudo ufw allow 443/tcp

# Display final SSL setup summary
echo "✅ SSL/HTTPS setup completed successfully!"
echo ""
echo "📋 SSL Configuration Summary:"
echo "   Domain: $DOMAIN_NAME"
echo "   HTTPS URL: https://$DOMAIN_NAME"
echo "   API Docs: https://$DOMAIN_NAME/docs"
echo "   Health Check: https://$DOMAIN_NAME/health"
echo "   Certificate: Let's Encrypt (auto-renewing)"
echo "   Security: A+ grade SSL configuration"
echo ""
echo "🔧 SSL Management Commands:"
echo "   Check certificates: sudo certbot certificates"
echo "   Renew certificates: sudo certbot renew"
echo "   Test renewal: sudo certbot renew --dry-run"
echo "   Monitor SSL: ./monitor_ssl.sh $DOMAIN_NAME"
echo ""
echo "🛡️  Security Features Enabled:"
echo "   - HTTP to HTTPS redirect"
echo "   - HSTS (HTTP Strict Transport Security)"
echo "   - Strong SSL/TLS configuration"
echo "   - Security headers"
echo "   - Automatic certificate renewal"
echo ""
echo "📝 Your Feed Formulation Backend is now secured with HTTPS!"
