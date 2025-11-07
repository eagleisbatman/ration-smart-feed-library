#!/usr/bin/env python3
"""
Feed Formulation Backend - Development Deployment Script

This script automates the deployment of the Feed Formulation Backend to development server.
It handles SSH connection, Docker operations, and provides rollback capability.

Usage:
    python scripts/deploy_to_dev.py

Features:
- SSH key-based authentication
- Real-time command output
- Error handling with rollback
- Deployment logging
- Health checks
"""

import os
import sys
import time
import logging
import argparse
import getpass
from datetime import datetime
from typing import List, Tuple, Optional
import subprocess

try:
    import paramiko
except ImportError:
    print("❌ paramiko library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

# Development Server Configuration
SERVER_CONFIG = {
    'host': '47.128.1.51',  # Development server IP
    'username': 'ubuntu',
    'ssh_key_path': os.path.expanduser('~/.ssh/id_rsa'),
    'project_dir': 'feed-formulation-be',
    'docker_image': 'feed-formulation-be:v3',
    'container_name': 'feed-formulation-be',
    'port': '8000',
    'github_username': None,  # Will be prompted
    'github_token': None      # Will be prompted
}

# Development Server Deployment Steps
DEPLOYMENT_STEPS = [
    {
        'name': 'Connect to development server',
        'command': 'echo "Connected to development server"',
        'rollback': None
    },
    {
        'name': 'Switch to jenkins user',
        'command': 'sudo su - jenkins -c "echo \'Switched to jenkins user\'"',
        'rollback': None
    },
    {
        'name': 'Navigate to project directory',
        'command': f'sudo su - jenkins -c "cd {SERVER_CONFIG["project_dir"]} && pwd"',
        'rollback': None
    },
    {
        'name': 'Pull latest code from GitHub',
        'command': None,  # Will be set dynamically with credentials
        'rollback': 'sudo su - jenkins -c "cd feed-formulation-be && git reset --hard HEAD~1"'
    },
    {
        'name': 'Stop existing container',
        'command': f'sudo su - jenkins -c "docker stop {SERVER_CONFIG["container_name"]} || echo \'No existing container to stop\'"',
        'rollback': f'sudo su - jenkins -c "docker start {SERVER_CONFIG["container_name"]}"'
    },
    {
        'name': 'Remove existing container',
        'command': f'sudo su - jenkins -c "docker rm {SERVER_CONFIG["container_name"]} || echo \'No existing container to remove\'"',
        'rollback': None
    },
    {
        'name': 'Remove existing image',
        'command': f'sudo su - jenkins -c "docker rmi {SERVER_CONFIG["docker_image"]} || echo \'No existing image to remove\'"',
        'rollback': None
    },
    {
        'name': 'Build new Docker image',
        'command': f'sudo su - jenkins -c "cd {SERVER_CONFIG["project_dir"]} && docker build -t {SERVER_CONFIG["docker_image"]} ."',
        'rollback': None
    },
    {
        'name': 'Run new container',
        'command': f'sudo su - jenkins -c "cd {SERVER_CONFIG["project_dir"]} && docker run -d --name {SERVER_CONFIG["container_name"]} -p {SERVER_CONFIG["port"]}:{SERVER_CONFIG["port"]} --env-file .env {SERVER_CONFIG["docker_image"]}"',
        'rollback': f'sudo su - jenkins -c "docker stop {SERVER_CONFIG["container_name"]} && docker rm {SERVER_CONFIG["container_name"]}"'
    },
    {
        'name': 'Verify container status',
        'command': 'sudo su - jenkins -c "docker ps"',
        'rollback': None
    }
]


class DeploymentLogger:
    """Handles logging for deployment operations"""
    
    def __init__(self, log_file: str = None):
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"deployment_log_{timestamp}.log"
        
        self.log_file = log_file
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)


class SSHDeployer:
    """Handles SSH connection and command execution"""
    
    def __init__(self, config: dict, logger: DeploymentLogger):
        self.config = config
        self.logger = logger
        self.ssh_client = None
        self.connected = False
        self.ssh_passphrase = None
    
    def connect(self) -> bool:
        """Establish SSH connection to the server"""
        try:
            self.logger.info(f"🔌 Connecting to {self.config['host']} as {self.config['username']}")
            
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load SSH key
            if not os.path.exists(self.config['ssh_key_path']):
                raise FileNotFoundError(f"SSH key not found: {self.config['ssh_key_path']}")
            
            # Prompt for SSH passphrase if needed
            if not self.ssh_passphrase:
                self.ssh_passphrase = getpass.getpass("🔐 Enter SSH key passphrase: ")
            
            # Try to connect with passphrase
            try:
                self.ssh_client.connect(
                    hostname=self.config['host'],
                    username=self.config['username'],
                    key_filename=self.config['ssh_key_path'],
                    passphrase=self.ssh_passphrase,
                    timeout=30
                )
            except paramiko.AuthenticationException:
                # If passphrase is wrong, prompt again
                self.logger.warning("❌ Invalid passphrase. Please try again.")
                self.ssh_passphrase = getpass.getpass("🔐 Enter SSH key passphrase: ")
                self.ssh_client.connect(
                    hostname=self.config['host'],
                    username=self.config['username'],
                    key_filename=self.config['ssh_key_path'],
                    passphrase=self.ssh_passphrase,
                    timeout=30
                )
            
            self.connected = True
            self.logger.info("✅ SSH connection established successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to server: {str(e)}")
            return False
    
    def execute_command(self, command: str, timeout: int = 300) -> Tuple[bool, str, str]:
        """Execute a command on the remote server"""
        if not self.connected:
            return False, "", "Not connected to server"
        
        try:
            self.logger.info(f"🚀 Executing: {command}")
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            
            # Read output
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            # Log output
            if stdout_data:
                self.logger.info(f"📤 Output: {stdout_data.strip()}")
            if stderr_data:
                self.logger.warning(f"⚠️  Errors: {stderr_data.strip()}")
            
            success = exit_code == 0
            if success:
                self.logger.info("✅ Command executed successfully")
            else:
                self.logger.error(f"❌ Command failed with exit code: {exit_code}")
            
            return success, stdout_data, stderr_data
            
        except Exception as e:
            self.logger.error(f"❌ Command execution failed: {str(e)}")
            return False, "", str(e)
    
    def disconnect(self):
        """Close SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            self.connected = False
            self.logger.info("🔌 SSH connection closed")


class DeploymentManager:
    """Manages the deployment process with rollback capability"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = DeploymentLogger()
        self.deployer = SSHDeployer(config, self.logger)
        self.completed_steps = []
        self.failed_step = None
        self.github_credentials = None
    
    def get_github_credentials(self):
        """Prompt for GitHub credentials"""
        if not self.github_credentials:
            self.logger.info("🔐 GitHub authentication required for git pull")
            username = input("📧 Enter GitHub username: ")
            token = getpass.getpass("🔑 Enter GitHub personal access token: ")
            self.github_credentials = {'username': username, 'token': token}
        return self.github_credentials
    
    def run_deployment(self) -> bool:
        """Run the complete deployment process to development server"""
        self.logger.info("🚀 Starting Feed Formulation Backend Deployment to Development Server")
        self.logger.info(f"📋 Target Development Server: {self.config['host']}")
        self.logger.info(f"📁 Project Directory: {self.config['project_dir']}")
        self.logger.info(f"🐳 Docker Image: {self.config['docker_image']}")
        self.logger.info(f"📝 Log File: {self.logger.log_file}")
        
        try:
            # Connect to server
            if not self.deployer.connect():
                return False
            
            # Execute deployment steps
            for i, step in enumerate(DEPLOYMENT_STEPS, 1):
                self.logger.info(f"\n📋 Step {i}/{len(DEPLOYMENT_STEPS)}: {step['name']}")
                
                # Handle special case for git pull with credentials
                if step['name'] == 'Pull latest code from GitHub':
                    github_creds = self.get_github_credentials()
                    # Set up git credentials and pull
                    git_command = f'''sudo su - jenkins -c "cd {self.config['project_dir']} && 
                    git config --local credential.helper store && 
                    echo 'https://{github_creds['username']}:{github_creds['token']}@github.com' > ~/.git-credentials && 
                    git pull origin v3.0"'''
                    success, stdout, stderr = self.deployer.execute_command(git_command)
                else:
                    success, stdout, stderr = self.deployer.execute_command(step['command'])
                
                if success:
                    self.completed_steps.append(step)
                    self.logger.info(f"✅ Step {i} completed successfully")
                else:
                    self.failed_step = step
                    self.logger.error(f"❌ Step {i} failed: {step['name']}")
                    self.logger.error(f"Error: {stderr}")
                    
                    # Attempt rollback
                    self.logger.warning("🔄 Attempting rollback...")
                    self.rollback()
                    return False
            
            # Health check
            if self.health_check():
                self.logger.info("🎉 Deployment completed successfully!")
                self.logger.info("✅ Application is running and healthy")
                return True
            else:
                self.logger.error("❌ Deployment completed but health check failed")
                self.rollback()
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Deployment failed with exception: {str(e)}")
            self.rollback()
            return False
        finally:
            self.deployer.disconnect()
    
    def rollback(self):
        """Rollback completed steps in reverse order"""
        if not self.completed_steps:
            self.logger.warning("⚠️  No completed steps to rollback")
            return
        
        self.logger.warning("🔄 Starting rollback process...")
        
        # Rollback in reverse order
        for step in reversed(self.completed_steps):
            if step.get('rollback'):
                self.logger.info(f"🔄 Rolling back: {step['name']}")
                success, stdout, stderr = self.deployer.execute_command(step['rollback'])
                if success:
                    self.logger.info(f"✅ Rollback successful: {step['name']}")
                else:
                    self.logger.error(f"❌ Rollback failed: {step['name']} - {stderr}")
    
    def health_check(self) -> bool:
        """Perform health check on the deployed application with retry logic"""
        import time
        import requests
        
        self.logger.info("🏥 Performing health check...")
        
        # Check if container is running
        success, stdout, stderr = self.deployer.execute_command('sudo su - jenkins -c "docker ps --filter name=feed-formulation-be --format \\"table {{.Names}}\\t{{.Status}}\\""')
        
        if not success or 'feed-formulation-be' not in stdout:
            self.logger.error("❌ Container is not running")
            return False
        
        self.logger.info("✅ Container is running")
        
        # Log container startup time for future reference
        container_start_time = time.time()
        self.logger.info(f"📊 Container started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(container_start_time))}")
        
        # Wait 10 seconds for container to fully initialize
        self.logger.info("⏳ Waiting 10 seconds for container to fully initialize...")
        time.sleep(10)
        
        # Perform health check with retry logic
        max_attempts = 3
        wait_time = 10  # seconds between attempts
        
        for attempt in range(1, max_attempts + 1):
            self.logger.info(f"🔍 Health check attempt {attempt}/{max_attempts}")
            
            try:
                # Check /docs endpoint with 5-second timeout
                response = requests.get(
                    f"http://{self.config['host']}:{self.config['port']}/docs", 
                    timeout=5
                )
                
                if response.status_code == 200:
                    self.logger.info("✅ Application is responding to HTTP requests")
                    self.logger.info(f"📊 Health check successful after {attempt} attempt(s)")
                    return True
                else:
                    self.logger.warning(f"⚠️  Application returned status code: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"⚠️  Health check timeout (5s) on attempt {attempt}")
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"⚠️  Connection refused on attempt {attempt}")
            except Exception as e:
                self.logger.warning(f"⚠️  Health check error on attempt {attempt}: {str(e)}")
            
            # If not the last attempt, wait before retrying
            if attempt < max_attempts:
                self.logger.info(f"⏳ Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
        
        # All attempts failed
        self.logger.error(f"❌ Health check failed after {max_attempts} attempts")
        self.logger.error("❌ Application is not responding properly")
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Deploy Feed Formulation Backend to Development Server')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed without running')
    parser.add_argument('--log-file', type=str, help='Custom log file path')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - Commands that would be executed:")
        for i, step in enumerate(DEPLOYMENT_STEPS, 1):
            if step['name'] == 'Pull latest code from GitHub':
                print(f"{i}. {step['name']}: git pull origin v3.0 (with GitHub credentials)")
            else:
                print(f"{i}. {step['name']}: {step['command']}")
        print("\n📋 Authentication Requirements:")
        print("   🔐 SSH Key Passphrase: Will be prompted")
        print("   🔑 GitHub Username: Will be prompted")
        print("   🔑 GitHub Personal Access Token: Will be prompted")
        return
    
    # Create deployment manager
    deployment_manager = DeploymentManager(SERVER_CONFIG)
    
    if args.log_file:
        deployment_manager.logger.log_file = args.log_file
    
    # Run deployment
    success = deployment_manager.run_deployment()
    
    if success:
        print("\n🎉 DEVELOPMENT DEPLOYMENT SUCCESSFUL!")
        print(f"📝 Log file: {deployment_manager.logger.log_file}")
        print(f"🌐 Development Server URL: http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}")
        print(f"🔗 Development Server: http://47.128.1.51/")
        sys.exit(0)
    else:
        print("\n❌ DEVELOPMENT DEPLOYMENT FAILED!")
        print(f"📝 Check log file: {deployment_manager.logger.log_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()
