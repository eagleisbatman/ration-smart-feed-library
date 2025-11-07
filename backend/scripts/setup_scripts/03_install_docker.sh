#!/bin/bash
# Docker and Docker Compose Installation Script
# This script installs Docker and Docker Compose on Ubuntu

set -e  # Exit on any error

echo "🐳 Starting Docker and Docker Compose installation..."

# Remove old Docker installations
echo "🧹 Removing old Docker installations..."
sudo apt remove -y docker docker-engine docker.io containerd runc || true

# Update package index
echo "📦 Updating package index..."
sudo apt update

# Install prerequisites
echo "🛠️  Installing prerequisites..."
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
echo "🔑 Adding Docker's official GPG key..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo "📋 Setting up Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index again
echo "📦 Updating package index with Docker repository..."
sudo apt update

# Install Docker Engine
echo "🐳 Installing Docker Engine..."
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group
echo "👤 Adding ubuntu user to docker group..."
sudo usermod -aG docker ubuntu

# Install Docker Compose (standalone)
echo "🐙 Installing Docker Compose (standalone)..."
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create symlink for docker-compose
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Start and enable Docker service
echo "🚀 Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

# Configure Docker daemon
echo "⚙️  Configuring Docker daemon..."
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true
}
EOF

# Restart Docker to apply configuration
sudo systemctl restart docker

# Create Docker networks for the application
echo "🌐 Creating Docker networks..."
sudo docker network create feed-formulation-network || true

# Set up Docker log rotation
echo "📝 Setting up Docker log rotation..."
sudo tee /etc/logrotate.d/docker > /dev/null <<EOF
/var/lib/docker/containers/*/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        /bin/kill -USR1 \$(cat /var/run/docker.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

# Verify installation
echo "✅ Verifying Docker installation..."
docker --version
docker-compose --version

# Test Docker installation
echo "🧪 Testing Docker installation..."
sudo docker run --rm hello-world

# Display Docker information
echo "📊 Docker Information:"
sudo docker info | grep -E "(Server Version|Storage Driver|Logging Driver|Cgroup Version)"

# Set up Docker cleanup cron job
echo "🧹 Setting up Docker cleanup cron job..."
sudo tee /etc/cron.d/docker-cleanup > /dev/null <<EOF
# Docker cleanup - runs daily at 2 AM
0 2 * * * root /usr/bin/docker system prune -f --volumes
EOF

echo "✅ Docker and Docker Compose installation completed successfully!"
echo "🔄 Please log out and log back in for group changes to take effect, or run:"
echo "   newgrp docker"
echo ""
echo "📋 Docker is now ready for your Feed Formulation Backend application!"
