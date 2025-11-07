#!/bin/bash
# GitHub Repository Setup Script
# This script clones the repository and configures Git credentials

set -e  # Exit on any error

echo "📁 Starting GitHub repository setup..."

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Installing..."
    sudo apt update
    sudo apt install -y git
fi

# Get GitHub credentials from environment or prompt
if [ -z "$GITHUB_USERNAME" ]; then
    echo "📧 GitHub username not provided in environment"
    echo "Please run this script with GITHUB_USERNAME and GITHUB_TOKEN environment variables"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "🔑 GitHub token not provided in environment"
    echo "Please run this script with GITHUB_USERNAME and GITHUB_TOKEN environment variables"
    exit 1
fi

if [ -z "$GITHUB_REPO" ]; then
    echo "📁 GitHub repository URL not provided in environment"
    echo "Please run this script with GITHUB_REPO environment variable"
    exit 1
fi

echo "📊 GitHub Configuration:"
echo "   Username: $GITHUB_USERNAME"
echo "   Repository: $GITHUB_REPO"

# Configure Git globally
echo "⚙️  Configuring Git globally..."
git config --global user.name "$GITHUB_USERNAME"
git config --global user.email "$GITHUB_USERNAME@users.noreply.github.com"
git config --global init.defaultBranch main
git config --global pull.rebase false

# Set up Git credential helper
echo "🔐 Setting up Git credential helper..."
git config --global credential.helper store

# Create credentials file
echo "📝 Creating Git credentials file..."
echo "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials

# Navigate to home directory
cd ~

# Clone the repository
echo "📥 Cloning repository..."
if [ -d "feed-formulation-be" ]; then
    echo "⚠️  Directory feed-formulation-be already exists. Removing..."
    rm -rf feed-formulation-be
fi

git clone "$GITHUB_REPO" feed-formulation-be
cd feed-formulation-be

# Checkout the correct branch (v3.0 based on your current setup)
echo "🌿 Checking out v3.0 branch..."
git checkout v3.0

# Verify repository
echo "✅ Verifying repository..."
echo "Repository URL: $(git remote get-url origin)"
echo "Current branch: $(git branch --show-current)"
echo "Latest commit: $(git log -1 --oneline)"

# Set up Git hooks (optional)
echo "🪝 Setting up Git hooks..."
mkdir -p .git/hooks

# Create pre-commit hook for basic checks
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook for basic checks

echo "Running pre-commit checks..."

# Check for large files
if git diff --cached --name-only | xargs -I {} find {} -size +10M 2>/dev/null; then
    echo "❌ Error: Large files (>10MB) detected. Please use Git LFS or remove them."
    exit 1
fi

# Check for sensitive files
if git diff --cached --name-only | grep -E '\.(env|key|pem|p12)$'; then
    echo "❌ Error: Sensitive files detected. Please remove them from staging."
    exit 1
fi

echo "✅ Pre-commit checks passed"
EOF

chmod +x .git/hooks/pre-commit

# Create post-commit hook for logging
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
# Post-commit hook for logging

echo "📝 Commit logged: $(git log -1 --oneline)"
echo "📅 Date: $(date)"
echo "👤 Author: $(git log -1 --pretty=format:'%an <%ae>')"
EOF

chmod +x .git/hooks/post-commit

# Set up repository permissions
echo "🔐 Setting up repository permissions..."
chmod -R 755 .
chmod 600 .git/config
chmod 600 ~/.git-credentials

# Create application directories
echo "📁 Creating application directories..."
mkdir -p logs
mkdir -p temp_work
mkdir -p result_html
mkdir -p diet_reports

# Set proper permissions for directories
chmod 755 logs temp_work result_html diet_reports

# Create .env template if it doesn't exist
echo "📝 Creating .env template..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Feed Formulation Backend - Environment Configuration
# Copy this file and update with your actual values

# Database Configuration
DATABASE_URL=postgresql://feed_user:feed_user_password@localhost:5432/feed_formulation
DB_HOST=localhost
DB_PORT=5432
DB_NAME=feed_formulation
DB_USER=feed_user
DB_PASSWORD=feed_user_password

# Application Configuration
APP_NAME=Feed Formulation Backend
APP_VERSION=v3.0
DEBUG=False
SECRET_KEY=your-secret-key-here
ENVIRONMENT=production

# Server Configuration
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Email Configuration (for PIN reset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com

# AWS Configuration (if using S3)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-s3-bucket

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Security Configuration
CORS_ORIGINS=["http://localhost:3000", "https://yourdomain.com"]
ALLOWED_HOSTS=["localhost", "127.0.0.1", "yourdomain.com"]
EOF
    echo "✅ .env template created"
else
    echo "⚠️  .env file already exists, skipping template creation"
fi

# Test Git configuration
echo "🧪 Testing Git configuration..."
git config --list | grep -E "(user\.|credential\.|remote\.)"

# Test repository access
echo "🧪 Testing repository access..."
git fetch origin
echo "✅ Repository access test successful"

# Display repository information
echo "📊 Repository Information:"
echo "   Location: $(pwd)"
echo "   Remote URL: $(git remote get-url origin)"
echo "   Current branch: $(git branch --show-current)"
echo "   Total commits: $(git rev-list --count HEAD)"
echo "   Last commit: $(git log -1 --pretty=format:'%h - %s (%an, %ar)')"

# Create a simple status script
echo "📝 Creating repository status script..."
cat > check_repo_status.sh << 'EOF'
#!/bin/bash
# Repository status checker

echo "📊 Feed Formulation Backend - Repository Status"
echo "=============================================="
echo "Location: $(pwd)"
echo "Remote URL: $(git remote get-url origin)"
echo "Current branch: $(git branch --show-current)"
echo "Last commit: $(git log -1 --pretty=format:'%h - %s (%an, %ar)')"
echo "Status: $(git status --porcelain | wc -l) uncommitted changes"
echo "Ahead/Behind: $(git status -sb | grep -o '\[.*\]')"
echo ""
echo "📁 Directory structure:"
ls -la
EOF

chmod +x check_repo_status.sh

echo "✅ GitHub repository setup completed successfully!"
echo ""
echo "📋 Repository is now ready with:"
echo "   - Git credentials configured"
echo "   - v3.0 branch checked out"
echo "   - Pre-commit hooks installed"
echo "   - .env template created"
echo "   - Application directories created"
echo "   - Status checker script created"
echo ""
echo "🔧 Next steps:"
echo "1. Update .env file with your actual configuration"
echo "2. Run database migrations when ready"
echo "3. Deploy the application"
echo ""
echo "📝 To check repository status: ./check_repo_status.sh"
