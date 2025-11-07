#!/bin/bash
# Application Deployment Script
# This script builds and deploys the FastAPI application using Docker

set -e  # Exit on any error

echo "🚀 Starting application deployment..."

# Navigate to application directory
cd ~/feed-formulation-be

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found. Are you in the correct directory?"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ .env file created from template"
        echo "⚠️  Please update .env file with your actual configuration before proceeding"
        exit 1
    else
        echo "❌ No .env template found. Please create .env file manually"
        exit 1
    fi
fi

# Load environment variables
echo "📝 Loading environment variables..."
source .env

# Stop and remove existing container if it exists
echo "🛑 Stopping existing container..."
docker stop feed-formulation-be 2>/dev/null || echo "No existing container to stop"
docker rm feed-formulation-be 2>/dev/null || echo "No existing container to remove"

# Remove existing image if it exists
echo "🗑️  Removing existing image..."
docker rmi feed-formulation-be:v3 2>/dev/null || echo "No existing image to remove"

# Build new Docker image
echo "🔨 Building Docker image..."
docker build -t feed-formulation-be:v3 .

# Verify image was built successfully
if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully"
else
    echo "❌ Docker image build failed"
    exit 1
fi

# Create Docker network if it doesn't exist
echo "🌐 Creating Docker network..."
docker network create feed-formulation-network 2>/dev/null || echo "Network already exists"

# Run the application container
echo "🚀 Starting application container..."
docker run -d \
    --name feed-formulation-be \
    --network feed-formulation-network \
    -p 8000:8000 \
    --env-file .env \
    --restart unless-stopped \
    --log-driver json-file \
    --log-opt max-size=10m \
    --log-opt max-file=3 \
    feed-formulation-be:v3

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 10

# Check if container is running
echo "🔍 Checking container status..."
if docker ps | grep -q "feed-formulation-be"; then
    echo "✅ Container is running"
else
    echo "❌ Container failed to start"
    echo "📋 Container logs:"
    docker logs feed-formulation-be
    exit 1
fi

# Wait for application to be ready
echo "⏳ Waiting for application to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
        echo "✅ Application is responding"
        break
    fi
    echo "⏳ Attempt $i/30: Application not ready yet..."
    sleep 2
done

# Test application endpoints
echo "🧪 Testing application endpoints..."

# Test health endpoint
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Health endpoint is working"
else
    echo "⚠️  Health endpoint not responding"
fi

# Test docs endpoint
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ API documentation is accessible"
else
    echo "⚠️  API documentation not accessible"
fi

# Test root endpoint
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ Root endpoint is working"
else
    echo "⚠️  Root endpoint not responding"
fi

# Display container information
echo "📊 Container Information:"
echo "   Name: feed-formulation-be"
echo "   Image: feed-formulation-be:v3"
echo "   Status: $(docker inspect --format='{{.State.Status}}' feed-formulation-be)"
echo "   Port: 8000"
echo "   Network: feed-formulation-network"

# Display container logs (last 20 lines)
echo "📋 Recent container logs:"
docker logs --tail 20 feed-formulation-be

# Create application management script
echo "📝 Creating application management script..."
cat > manage_app.sh << 'EOF'
#!/bin/bash
# Application management script

case "$1" in
    start)
        echo "🚀 Starting application..."
        docker start feed-formulation-be
        ;;
    stop)
        echo "🛑 Stopping application..."
        docker stop feed-formulation-be
        ;;
    restart)
        echo "🔄 Restarting application..."
        docker restart feed-formulation-be
        ;;
    status)
        echo "📊 Application status:"
        docker ps --filter name=feed-formulation-be
        ;;
    logs)
        echo "📋 Application logs:"
        docker logs -f feed-formulation-be
        ;;
    update)
        echo "🔄 Updating application..."
        git pull origin v3.0
        docker stop feed-formulation-be
        docker rm feed-formulation-be
        docker rmi feed-formulation-be:v3
        docker build -t feed-formulation-be:v3 .
        docker run -d --name feed-formulation-be --network feed-formulation-network -p 8000:8000 --env-file .env --restart unless-stopped feed-formulation-be:v3
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|update}"
        exit 1
        ;;
esac
EOF

chmod +x manage_app.sh

# Set up log rotation for Docker logs
echo "📝 Setting up Docker log rotation..."
sudo tee /etc/logrotate.d/docker-containers > /dev/null <<EOF
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

# Create monitoring script
echo "📝 Creating monitoring script..."
cat > monitor_app.sh << 'EOF'
#!/bin/bash
# Application monitoring script

echo "📊 Feed Formulation Backend - Application Monitor"
echo "================================================"

# Container status
echo "🐳 Container Status:"
docker ps --filter name=feed-formulation-be --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Application health
echo ""
echo "🏥 Application Health:"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Application is healthy"
else
    echo "❌ Application is not responding"
fi

# Resource usage
echo ""
echo "💻 Resource Usage:"
docker stats feed-formulation-be --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Recent logs
echo ""
echo "📋 Recent Logs (last 10 lines):"
docker logs --tail 10 feed-formulation-be
EOF

chmod +x monitor_app.sh

# Test Nginx proxy
echo "🧪 Testing Nginx proxy..."
if curl -s http://localhost/health > /dev/null 2>&1; then
    echo "✅ Nginx proxy is working"
else
    echo "⚠️  Nginx proxy not responding (this is expected if Nginx isn't configured yet)"
fi

# Display deployment summary
echo "✅ Application deployment completed successfully!"
echo ""
echo "📋 Deployment Summary:"
echo "   Application: Feed Formulation Backend v3.0"
echo "   Container: feed-formulation-be"
echo "   Port: 8000"
echo "   Status: Running"
echo "   Network: feed-formulation-network"
echo ""
echo "🌐 Access URLs:"
echo "   Direct: http://$(curl -s ifconfig.me):8000"
echo "   API Docs: http://$(curl -s ifconfig.me):8000/docs"
echo "   Health: http://$(curl -s ifconfig.me):8000/health"
echo ""
echo "🔧 Management Commands:"
echo "   Start: ./manage_app.sh start"
echo "   Stop: ./manage_app.sh stop"
echo "   Restart: ./manage_app.sh restart"
echo "   Status: ./manage_app.sh status"
echo "   Logs: ./manage_app.sh logs"
echo "   Monitor: ./monitor_app.sh"
echo ""
echo "📝 Next Steps:"
echo "1. Test all API endpoints"
echo "2. Run database migrations when ready"
echo "3. Configure SSL/HTTPS if needed"
echo "4. Set up monitoring and alerts"
