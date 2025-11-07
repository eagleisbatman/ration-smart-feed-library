# Feed Formulation Backend - New Server Setup

This directory contains comprehensive scripts to set up a fresh AWS EC2 instance for the Feed Formulation Backend application.

## 📋 Overview

The setup process automates the complete installation and configuration of:
- Ubuntu system updates and security hardening
- Docker and Docker Compose
- PostgreSQL database server
- Nginx web server with SSL support
- Firewall configuration
- GitHub repository setup
- FastAPI application deployment
- SSL/HTTPS with Let's Encrypt
- Health monitoring and logging

## 🚀 Quick Start

### Prerequisites

1. **New AWS EC2 Instance** (Ubuntu 20.04/22.04)
2. **SSH Key** (same as your current setup)
3. **GitHub Credentials** (username and personal access token)
4. **Domain Name** (optional, for SSL)

### Usage

```bash
# Run the complete setup
python scripts/setup_new_server.py --host <YOUR_SERVER_IP>

# Example
python scripts/setup_new_server.py --host 54.123.45.67
```

### What You'll Need to Provide

The script will prompt you for:
- SSH key passphrase (if your key has one)
- GitHub username
- GitHub personal access token
- GitHub repository URL
- Domain name (optional, for SSL)
- Email address (required if using SSL)

## 📁 Scripts Overview

### 1. `01_connect_test.sh`
- Tests SSH connection
- Displays server information
- Checks system resources
- Verifies network connectivity

### 2. `02_system_update.sh`
- Updates Ubuntu packages
- Installs essential tools
- Configures automatic security updates
- Sets up fail2ban for SSH protection
- Configures log rotation

### 3. `03_install_docker.sh`
- Installs Docker Engine
- Installs Docker Compose
- Configures Docker daemon
- Sets up Docker networks
- Configures log rotation

### 4. `04_install_postgresql.sh`
- Installs PostgreSQL
- Creates application database
- Creates application user
- Configures performance settings
- Sets up automated backups

### 5. `05_install_nginx.sh`
- Installs Nginx
- Creates application configuration
- Sets up reverse proxy
- Configures static file serving
- Sets up log rotation

### 6. `06_configure_firewall.sh`
- Configures UFW firewall
- Allows necessary ports
- Sets up rate limiting
- Enables logging
- Configures security rules

### 7. `07_setup_github.sh`
- Clones your repository
- Configures Git credentials
- Sets up Git hooks
- Creates application directories
- Creates .env template

### 8. `08_deploy_application.sh`
- Builds Docker image
- Deploys application container
- Tests application endpoints
- Creates management scripts
- Sets up monitoring

### 9. `09_setup_ssl.sh`
- Installs Certbot
- Obtains SSL certificate
- Configures HTTPS
- Sets up auto-renewal
- Configures security headers

### 10. `10_health_check.sh`
- Comprehensive system health check
- Service status verification
- Application endpoint testing
- Resource usage monitoring
- Log file verification

## 🔧 Manual Setup (Alternative)

If you prefer to run scripts manually:

```bash
# 1. Connect to your server
ssh -i ~/.ssh/id_rsa ubuntu@<YOUR_SERVER_IP>

# 2. Run each script in order
bash /tmp/01_connect_test.sh
bash /tmp/02_system_update.sh
bash /tmp/03_install_docker.sh
bash /tmp/04_install_postgresql.sh
bash /tmp/05_install_nginx.sh
bash /tmp/06_configure_firewall.sh

# 3. Set environment variables for GitHub setup
export GITHUB_USERNAME="your-username"
export GITHUB_TOKEN="your-token"
export GITHUB_REPO="https://github.com/your-username/feed-formulation-be.git"
bash /tmp/07_setup_github.sh

# 4. Deploy application
bash /tmp/08_deploy_application.sh

# 5. Setup SSL (optional)
export DOMAIN_NAME="yourdomain.com"
export EMAIL="your-email@example.com"
bash /tmp/09_setup_ssl.sh

# 6. Health check
bash /tmp/10_health_check.sh
```

## 📊 What Gets Installed

### System Software
- **Docker**: Container runtime
- **Docker Compose**: Multi-container orchestration
- **PostgreSQL**: Database server
- **Nginx**: Web server and reverse proxy
- **Certbot**: SSL certificate management
- **UFW**: Firewall management
- **Fail2ban**: Intrusion prevention

### Application Components
- **FastAPI Backend**: Your application
- **Database**: PostgreSQL with application schema
- **Web Server**: Nginx with SSL support
- **Monitoring**: Health checks and logging
- **Security**: Firewall and SSL certificates

## 🔒 Security Features

- **SSH Hardening**: Rate limiting, key-only auth
- **Firewall**: UFW with minimal open ports
- **SSL/TLS**: Let's Encrypt certificates
- **Security Headers**: HSTS, CSP, XSS protection
- **Fail2ban**: SSH brute force protection
- **Log Monitoring**: Automated log rotation

## 📝 Configuration Files

### Database
- **Host**: localhost
- **Port**: 5432
- **Database**: feed_formulation
- **User**: feed_user
- **Password**: feed_user_password

### Application
- **Port**: 8000
- **Workers**: 4
- **Log Level**: INFO
- **Environment**: production

### Nginx
- **HTTP Port**: 80
- **HTTPS Port**: 443
- **SSL**: Let's Encrypt
- **Proxy**: FastAPI on port 8000

## 🚨 Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Check SSH key permissions: `chmod 600 ~/.ssh/id_rsa`
   - Verify server IP and security groups
   - Check SSH key passphrase

2. **Docker Build Failed**
   - Check internet connectivity
   - Verify Docker Hub access
   - Check available disk space

3. **Application Not Responding**
   - Check container status: `docker ps`
   - View container logs: `docker logs feed-formulation-be`
   - Check port availability: `netstat -tlnp`

4. **SSL Certificate Failed**
   - Verify domain DNS points to server
   - Check firewall allows port 80/443
   - Ensure email is valid

### Useful Commands

```bash
# Check application status
./manage_app.sh status

# View application logs
./manage_app.sh logs

# Restart application
./manage_app.sh restart

# Monitor system health
./monitor_app.sh

# Check SSL status
./monitor_ssl.sh yourdomain.com
```

## 📋 Post-Setup Checklist

- [ ] Application is responding on HTTP
- [ ] API documentation is accessible
- [ ] Database is running and accessible
- [ ] SSL certificate is working (if configured)
- [ ] Firewall is properly configured
- [ ] Logs are being generated
- [ ] Health checks are passing
- [ ] Run database migrations when ready

## 🔄 Maintenance

### Regular Tasks
- Monitor disk space and memory usage
- Check SSL certificate expiry
- Review application logs
- Update system packages
- Backup database

### Updates
- Pull latest code: `git pull origin v3.0`
- Rebuild and deploy: `./manage_app.sh update`
- Check health: `./monitor_app.sh`

## 📞 Support

If you encounter issues:
1. Check the health check script output
2. Review application logs
3. Verify all services are running
4. Check firewall and network settings
5. Ensure all environment variables are set

## 🎯 Next Steps

After successful setup:
1. **Run Database Migrations**: Execute your migration scripts
2. **Test API Endpoints**: Verify all functionality
3. **Configure Monitoring**: Set up alerts and monitoring
4. **Backup Strategy**: Implement regular backups
5. **Performance Tuning**: Optimize based on usage

---

**Note**: This setup creates a production-ready environment. Make sure to update all default passwords and configure your specific application settings in the `.env` file.
