# Deployment Guide for Feed Formulation Backend

## Overview

This guide covers deploying the Feed Formulation Backend with automatic cron job setup for report cleanup.

## Prerequisites

- Docker installed on your server
- SSH access to your cloud server
- Your application code deployed to the server

## Deployment Options

### Option 1: Full Deployment with Cron Setup

Use `deploy_with_cron.sh` for a complete deployment including Docker build and cron setup.

### Option 2: Cron Setup Only

Use `setup_cron_only.sh` if you already have the Docker container running.

## Step-by-Step Deployment

### 1. Upload Files to Server

First, upload your application files to the server:

```bash
# On your local machine
scp -r /path/to/feed-formulation-be user@your-server:/opt/
```

### 2. SSH into Your Server

```bash
ssh user@your-server
```

### 3. Navigate to Application Directory

```bash
cd /opt/feed-formulation-be
```

### 4. Update Configuration

Edit the deployment script to match your server setup:

```bash
# Edit deploy_with_cron.sh or setup_cron_only.sh
nano deploy_with_cron.sh
```

Update these variables:
- `APP_DIR`: Your application directory path
- `DOCKER_CONTAINER_NAME`: Your Docker container name
- `DOCKER_IMAGE_NAME`: Your Docker image name

### 5. Make Scripts Executable

```bash
chmod +x deploy_with_cron.sh setup_cron_only.sh
```

### 6. Run Deployment

#### For Full Deployment:
```bash
sudo ./deploy_with_cron.sh
```

#### For Cron Setup Only:
```bash
sudo ./setup_cron_only.sh
```

## What the Scripts Do

### deploy_with_cron.sh
1. ✅ Checks prerequisites (Docker, etc.)
2. ✅ Creates necessary directories
3. ✅ Stops existing containers
4. ✅ Builds and starts Docker container
5. ✅ Sets up cron job for cleanup
6. ✅ Tests the cleanup script
7. ✅ Configures log rotation
8. ✅ Provides deployment summary

### setup_cron_only.sh
1. ✅ Checks if Docker container is running
2. ✅ Creates log directory
3. ✅ Sets up cron job for cleanup
4. ✅ Tests the cleanup script
5. ✅ Configures log rotation
6. ✅ Provides setup summary

## Configuration Variables

Update these in the scripts before running:

```bash
# Application paths
APP_DIR="/opt/feed-formulation-be"  # Your app directory
DOCKER_CONTAINER_NAME="feed-formulation-app"  # Your container name
DOCKER_IMAGE_NAME="feed-formulation-backend"  # Your image name

# Logging
LOG_DIR="$APP_DIR/logs"
CRON_LOG_FILE="$LOG_DIR/cleanup.log"
```

## Cron Job Details

The cron job runs every 3 hours and:
- Executes `cleanup_old_reports.py` inside the Docker container
- Deletes reports older than 5 hours that haven't been saved to AWS
- Logs output to `$LOG_DIR/cleanup.log`

Cron schedule: `0 */3 * * *` (every 3 hours at minute 0)

## Verification Steps

After deployment, verify everything is working:

### 1. Check Application Status
```bash
# Check if container is running
docker ps

# Check application logs
docker logs feed-formulation-app

# Test health endpoint
curl http://localhost:8000/health
```

### 2. Check Cron Job
```bash
# View cron jobs
crontab -l

# Check cron logs
tail -f /opt/feed-formulation-be/logs/cleanup.log
```

### 3. Test Cleanup Script
```bash
# Manual test
docker exec feed-formulation-app python cleanup_old_reports.py
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   # Run with sudo
   sudo ./deploy_with_cron.sh
   ```

2. **Docker Container Not Found**
   ```bash
   # Check container name
   docker ps -a
   # Update container name in script
   ```

3. **Cron Job Not Running**
   ```bash
   # Check cron service
   sudo service cron status
   
   # Check cron logs
   sudo tail -f /var/log/cron
   ```

4. **Cleanup Script Fails**
   ```bash
   # Check database connection
   docker exec feed-formulation-app python -c "from dependencies import get_db; print('DB OK')"
   
   # Check environment variables
   docker exec feed-formulation-app env | grep AWS
   ```

### Log Files

- **Application logs**: `docker logs feed-formulation-app`
- **Cron logs**: `/opt/feed-formulation-be/logs/cleanup.log`
- **System cron logs**: `/var/log/cron`

## Maintenance

### Updating the Application
```bash
# Stop container
docker stop feed-formulation-app

# Pull new code and rebuild
git pull
docker build -t feed-formulation-backend .

# Start container
docker start feed-formulation-app

# Re-run cron setup if needed
./setup_cron_only.sh
```

### Monitoring
```bash
# Check cron job status
crontab -l

# Monitor cleanup logs
tail -f /opt/feed-formulation-be/logs/cleanup.log

# Check disk space
df -h

# Check database size
docker exec feed-formulation-app psql -U postgres -d postgres -c "SELECT pg_size_pretty(pg_database_size('postgres'));"
```

## Security Considerations

1. **File Permissions**: Ensure `.env` file has restricted permissions
2. **Database Access**: Use strong database passwords
3. **AWS Credentials**: Keep AWS credentials secure
4. **Log Rotation**: Logs are automatically rotated to prevent disk space issues

## Support

If you encounter issues:
1. Check the logs mentioned above
2. Verify all configuration variables
3. Ensure Docker and cron services are running
4. Test the cleanup script manually
