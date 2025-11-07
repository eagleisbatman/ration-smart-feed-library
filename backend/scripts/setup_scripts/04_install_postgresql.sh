#!/bin/bash
# PostgreSQL Installation Script
# This script installs PostgreSQL database server

set -e  # Exit on any error

echo "🐘 Starting PostgreSQL installation..."

# Update package index
echo "📦 Updating package index..."
sudo apt update

# Install PostgreSQL
echo "🐘 Installing PostgreSQL..."
sudo apt install -y postgresql postgresql-contrib

# Start and enable PostgreSQL service
echo "🚀 Starting PostgreSQL service..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Get PostgreSQL version
POSTGRES_VERSION=$(sudo -u postgres psql -t -c "SELECT version();" | grep -oP '\d+\.\d+' | head -1)
echo "📊 PostgreSQL version: $POSTGRES_VERSION"

# Configure PostgreSQL
echo "⚙️  Configuring PostgreSQL..."

# Set up PostgreSQL configuration
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres_admin_password';"

# Create application database and user
echo "🗄️  Creating application database and user..."
sudo -u postgres psql <<EOF
-- Create database
CREATE DATABASE feed_formulation;

-- Create user
CREATE USER feed_user WITH PASSWORD 'feed_user_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE feed_formulation TO feed_user;

-- Grant schema privileges
\c feed_formulation;
GRANT ALL ON SCHEMA public TO feed_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO feed_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO feed_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO feed_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO feed_user;

-- Exit
\q
EOF

# Configure PostgreSQL for remote connections (if needed)
echo "🌐 Configuring PostgreSQL for connections..."

# Backup original configuration
sudo cp /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf.backup
sudo cp /etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf /etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf.backup

# Update postgresql.conf for better performance
sudo tee -a /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf > /dev/null <<EOF

# Performance tuning for Feed Formulation Backend
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

# Connection settings
max_connections = 100
listen_addresses = 'localhost'

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
EOF

# Update pg_hba.conf for authentication
sudo tee /etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf > /dev/null <<EOF
# PostgreSQL Client Authentication Configuration File
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     md5

# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5

# Allow connections from localhost for application
host    feed_formulation feed_user      127.0.0.1/32            md5
host    feed_formulation feed_user      ::1/128                 md5
EOF

# Restart PostgreSQL to apply configuration
echo "🔄 Restarting PostgreSQL to apply configuration..."
sudo systemctl restart postgresql

# Set up PostgreSQL log rotation
echo "📝 Setting up PostgreSQL log rotation..."
sudo tee /etc/logrotate.d/postgresql > /dev/null <<EOF
/var/log/postgresql/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 postgres postgres
    postrotate
        /bin/kill -HUP \$(cat /var/run/postgresql/*.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

# Create backup directory
echo "💾 Creating backup directory..."
sudo mkdir -p /var/backups/postgresql
sudo chown postgres:postgres /var/backups/postgresql

# Set up automated backups
echo "🔄 Setting up automated backups..."
sudo tee /etc/cron.d/postgresql-backup > /dev/null <<EOF
# PostgreSQL backup - runs daily at 3 AM
0 3 * * * postgres /usr/bin/pg_dump -h localhost -U postgres feed_formulation > /var/backups/postgresql/feed_formulation_\$(date +\%Y\%m\%d_\%H\%M\%S).sql
EOF

# Test database connection
echo "🧪 Testing database connection..."
sudo -u postgres psql -c "SELECT version();" > /dev/null
echo "✅ PostgreSQL connection test successful"

# Display database information
echo "📊 Database Information:"
echo "Database: feed_formulation"
echo "User: feed_user"
echo "Host: localhost"
echo "Port: 5432"
echo "Status: $(sudo systemctl is-active postgresql)"

# Show database size
DB_SIZE=$(sudo -u postgres psql -t -c "SELECT pg_size_pretty(pg_database_size('feed_formulation'));" | xargs)
echo "Database size: $DB_SIZE"

echo "✅ PostgreSQL installation completed successfully!"
echo ""
echo "📋 Database credentials:"
echo "   Database: feed_formulation"
echo "   Username: feed_user"
echo "   Password: feed_user_password"
echo "   Host: localhost"
echo "   Port: 5432"
echo ""
echo "🔧 To connect to the database:"
echo "   psql -h localhost -U feed_user -d feed_formulation"
echo ""
echo "📝 Note: You can run database migrations later when ready!"
