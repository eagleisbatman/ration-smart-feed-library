#!/bin/bash
# Complete Server Setup Orchestration Script
# This script runs all setup scripts in the correct order for a fresh server installation

set -e  # Exit on any error

echo "🚀 Feed Formulation Backend - Complete Server Setup"
echo "=================================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please do not run this script as root. Use a regular user with sudo privileges."
    exit 1
fi

# Check if we're on Ubuntu
if ! command -v lsb_release &> /dev/null || ! lsb_release -d | grep -q "Ubuntu"; then
    echo "❌ This script is designed for Ubuntu. Please run on an Ubuntu system."
    exit 1
fi

# Display server information
echo "📊 Server Information:"
echo "   OS: $(lsb_release -d | cut -f2)"
echo "   Kernel: $(uname -r)"
echo "   Architecture: $(uname -m)"
echo "   User: $(whoami)"
echo ""

# Check for .env file and load it if it exists
if [ -f ".env" ]; then
    echo "📝 Loading environment variables from .env file..."
    source .env
    echo "✅ .env file loaded successfully"
elif [ -f "/home/ubuntu/.env" ]; then
    echo "📝 Loading environment variables from /home/ubuntu/.env file..."
    source /home/ubuntu/.env
    echo "✅ .env file loaded successfully"
else
    echo "⚠️  No .env file found. Using environment variables from shell session."
fi

# Check if required environment variables are set
echo "🔍 Checking environment variables..."

# Required variables
REQUIRED_VARS=("GITHUB_USERNAME" "GITHUB_TOKEN" "GITHUB_REPO")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please set these variables before running the script:"
    echo ""
    echo "Option 1: Using .env file (Recommended):"
    echo "   Create a .env file with:"
    echo "   GITHUB_USERNAME=your-username"
    echo "   GITHUB_TOKEN=your-personal-access-token"
    echo "   GITHUB_REPO=https://github.com/your-username/feed-formulation-be.git"
    echo "   DOMAIN_NAME=yourdomain.com  # Optional, for SSL"
    echo "   EMAIL=your-email@example.com  # Optional, for SSL"
    echo ""
    echo "Option 2: Using environment variables:"
    echo "   export GITHUB_USERNAME=\"your-username\""
    echo "   export GITHUB_TOKEN=\"your-personal-access-token\""
    echo "   export GITHUB_REPO=\"https://github.com/your-username/feed-formulation-be.git\""
    echo ""
    echo "Optional variables:"
    echo "   export DOMAIN_NAME=\"yourdomain.com\"  # For SSL setup"
    echo "   export EMAIL=\"your-email@example.com\"  # For SSL setup"
    exit 1
fi

# Optional variables
if [ -z "$DOMAIN_NAME" ]; then
    echo "⚠️  DOMAIN_NAME not set. SSL setup will be skipped."
fi

if [ -z "$EMAIL" ]; then
    echo "⚠️  EMAIL not set. SSL setup will be skipped."
fi

echo "✅ Environment variables check passed"
echo ""

# Confirmation prompt
echo "⚠️  This script will install and configure:"
echo "   - System updates and security hardening"
echo "   - Docker and Docker Compose"
echo "   - PostgreSQL database"
echo "   - Nginx web server"
echo "   - Firewall configuration"
echo "   - GitHub repository setup"
echo "   - FastAPI application deployment"
if [ -n "$DOMAIN_NAME" ] && [ -n "$EMAIL" ]; then
    echo "   - SSL/HTTPS with Let's Encrypt"
fi
echo ""

read -p "Do you want to proceed with the complete setup? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Setup cancelled by user"
    exit 1
fi

echo ""
echo "🚀 Starting complete server setup..."
echo "===================================="
echo ""

# Function to run a script with error handling
run_script() {
    local script_name="$1"
    local script_path="$2"
    local description="$3"
    
    echo "📋 Running: $description"
    echo "   Script: $script_name"
    echo "   Time: $(date)"
    echo ""
    
    if [ -f "$script_path" ]; then
        if bash "$script_path"; then
            echo "✅ $description completed successfully"
        else
            echo "❌ $description failed"
            echo "   Please check the error messages above and fix any issues."
            echo "   You can continue from this point by running the remaining scripts manually."
            exit 1
        fi
    else
        echo "❌ Script not found: $script_path"
        exit 1
    fi
    
    echo ""
    echo "⏳ Waiting 5 seconds before next step..."
    sleep 5
    echo ""
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run all setup scripts in order
echo "🔄 Step 1/11: Connection Test"
run_script "01_connect_test.sh" "$SCRIPT_DIR/01_connect_test.sh" "Connection test and system information"

echo "🔄 Step 2/11: System Update"
run_script "02_system_update.sh" "$SCRIPT_DIR/02_system_update.sh" "System updates and security hardening"

echo "🔄 Step 3/11: Docker Installation"
run_script "03_install_docker.sh" "$SCRIPT_DIR/03_install_docker.sh" "Docker and Docker Compose installation"

echo "🔄 Step 4/11: PostgreSQL Installation"
run_script "04_install_postgresql.sh" "$SCRIPT_DIR/04_install_postgresql.sh" "PostgreSQL database installation"

echo "🔄 Step 5/11: Nginx Installation"
run_script "05_install_nginx.sh" "$SCRIPT_DIR/05_install_nginx.sh" "Nginx web server installation"

echo "🔄 Step 6/11: Firewall Configuration"
run_script "06_configure_firewall.sh" "$SCRIPT_DIR/06_configure_firewall.sh" "Firewall configuration and security"

echo "🔄 Step 7/11: GitHub Repository Setup"
run_script "07_setup_github.sh" "$SCRIPT_DIR/07_setup_github.sh" "GitHub repository cloning and configuration"

echo "🔄 Step 8/11: Application Deployment"
run_script "08_deploy_application.sh" "$SCRIPT_DIR/08_deploy_application.sh" "FastAPI application deployment"

# Optional SSL setup
if [ -n "$DOMAIN_NAME" ] && [ -n "$EMAIL" ]; then
    echo "🔄 Step 9/11: SSL Setup"
    run_script "09_setup_ssl.sh" "$SCRIPT_DIR/09_setup_ssl.sh" "SSL certificate setup with Let's Encrypt"
else
    echo "⏭️  Step 9/11: SSL Setup (Skipped - DOMAIN_NAME or EMAIL not set)"
fi

echo "🔄 Step 10/11: Health Check"
run_script "10_health_check.sh" "$SCRIPT_DIR/10_health_check.sh" "System health check and verification"

echo "🔄 Step 11/11: Database Schema Creation"
run_script "11_create_database.sh" "$SCRIPT_DIR/11_create_database.sh" "Database schema creation and initial data"

# Final summary
echo ""
echo "🎉 Complete Server Setup Finished Successfully!"
echo "================================================"
echo ""

echo "📋 What was installed:"
echo "   ✅ System updates and security hardening"
echo "   ✅ Docker and Docker Compose"
echo "   ✅ PostgreSQL database"
echo "   ✅ Nginx web server"
echo "   ✅ Firewall configuration"
echo "   ✅ GitHub repository setup"
echo "   ✅ FastAPI application deployment"
if [ -n "$DOMAIN_NAME" ] && [ -n "$EMAIL" ]; then
    echo "   ✅ SSL/HTTPS with Let's Encrypt"
fi
echo "   ✅ Database schema and initial data"
echo ""

echo "🌐 Access Information:"
echo "   Server IP: $(curl -s ifconfig.me 2>/dev/null || echo 'Unable to determine')"
echo "   Application: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')"
echo "   API Documentation: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')/docs"
echo "   Health Check: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')/health"
if [ -n "$DOMAIN_NAME" ]; then
    echo "   HTTPS URL: https://$DOMAIN_NAME"
    echo "   HTTPS API Docs: https://$DOMAIN_NAME/docs"
fi
echo ""

echo "🔧 Management Commands:"
echo "   Application status: ./manage_app.sh status"
echo "   View logs: ./manage_app.sh logs"
echo "   Restart app: ./manage_app.sh restart"
echo "   System health: ./monitor_app.sh"
if [ -n "$DOMAIN_NAME" ]; then
    echo "   SSL status: ./monitor_ssl.sh $DOMAIN_NAME"
fi
echo ""

echo "📝 Next Steps:"
echo "   1. Test all API endpoints"
echo "   2. Run database migrations if needed"
echo "   3. Configure monitoring and alerts"
echo "   4. Set up regular backups"
echo ""

echo "🎯 Your Feed Formulation Backend is now ready for production!"
echo ""
echo "⚠️  Important Notes:"
echo "   - Change default passwords in production"
echo "   - Configure your .env file with actual values"
echo "   - Set up regular backups"
echo "   - Monitor system resources"
echo "   - Keep system updated"
echo ""

echo "📞 Support:"
echo "   If you encounter issues, check the logs and health status"
echo "   Review the setup scripts for troubleshooting"
echo "   Ensure all services are running properly"
echo ""

echo "✅ Setup completed at: $(date)"
