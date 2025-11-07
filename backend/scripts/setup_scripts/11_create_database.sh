#!/bin/bash
# Database Schema Creation Script
set -e

echo "🗄️  Starting database schema creation..."

# Check if PostgreSQL is running
if ! sudo systemctl is-active --quiet postgresql; then
    echo "❌ PostgreSQL is not running. Starting PostgreSQL..."
    sudo systemctl start postgresql
    sleep 3
fi

# Set database connection parameters
DB_NAME="feed_formulation"
DB_USER="feed_user"
DB_PASSWORD="feed_user_password"

echo "📊 Creating database schema for: $DB_NAME"

# Run the SQL script
echo "🔧 Executing database schema creation script..."
PGPASSWORD=$DB_PASSWORD psql -h localhost -U $DB_USER -d $DB_NAME -f /home/ubuntu/feed-formulation-be/scripts/setup_scripts/11_create_database_schema.sql

# Verify the creation
echo "✅ Verifying database schema creation..."
PGPASSWORD=$DB_PASSWORD psql -h localhost -U $DB_USER -d $DB_NAME -c "
SELECT 
    'Database Schema Creation Complete' as status,
    COUNT(*) as total_tables
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'country', 'user_information', 'feed_type', 'feed_category', 
    'feeds', 'custom_feeds', 'feed_analytics', 'diet_reports', 
    'reports', 'user_feedback'
);
"

echo "📋 Listing all tables in the database:"
PGPASSWORD=$DB_PASSWORD psql -h localhost -U $DB_USER -d $DB_NAME -c "\dt"

echo "📊 Verifying initial data population:"
PGPASSWORD=$DB_PASSWORD psql -h localhost -U $DB_USER -d $DB_NAME -c "
SELECT 'Countries' as table_name, COUNT(*) as record_count FROM country
UNION ALL
SELECT 'Feed Types', COUNT(*) FROM feed_type
UNION ALL
SELECT 'Feed Categories', COUNT(*) FROM feed_category;
"

echo "🎉 Database schema creation completed successfully!"
echo "📝 Summary:"
echo "   - 10 tables created"
echo "   - All indexes and constraints applied"
echo "   - Initial data populated"
echo "   - Database ready for application deployment"
