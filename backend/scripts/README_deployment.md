# Feed Formulation Backend - Production Deployment

This directory contains automated deployment scripts for the Feed Formulation Backend to AWS production server.

## Files

- `deploy_to_production.py` - Main deployment script
- `deployment_requirements.txt` - Python dependencies for deployment
- `README_deployment.md` - This documentation

## Prerequisites

1. **SSH Key Setup**: Ensure you have SSH key-based authentication set up for `ubuntu@47.128.1.51`
2. **SSH Key Location**: The script expects your private key at `~/.ssh/id_rsa`
3. **SSH Key Passphrase**: Your SSH key must have a passphrase (script will prompt for it)
4. **GitHub Credentials**: You need a GitHub Personal Access Token for git pull operations
5. **Python Dependencies**: Install required packages

## Installation

1. Install deployment dependencies:
```bash
pip install -r scripts/deployment_requirements.txt
```

## Usage

### Basic Deployment
```bash
python scripts/deploy_to_production.py
```

### Dry Run (Preview Commands)
```bash
python scripts/deploy_to_production.py --dry-run
```

### Custom Log File
```bash
python scripts/deploy_to_production.py --log-file my_deployment.log
```

## Authentication

The script will prompt you for:

1. **SSH Key Passphrase** - Enter the passphrase for your SSH private key
2. **GitHub Username** - Your GitHub username
3. **GitHub Personal Access Token** - Your GitHub personal access token (not password)

### Creating GitHub Personal Access Token

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (Full control of private repositories)
4. Copy the generated token (you won't see it again)

## What the Script Does

The deployment script automates the following steps:

1. **Connect to Server** - SSH to `ubuntu@47.128.1.51` (prompts for passphrase)
2. **Switch User** - Switch to `jenkins` user
3. **Navigate** - Go to `feed-formulation-be` directory
4. **Pull Code** - `git pull origin v3.0` (with GitHub credentials)
5. **Stop Container** - `docker stop feed-formulation-be`
6. **Remove Container** - `docker rm feed-formulation-be`
7. **Remove Image** - `docker rmi feed-formulation-be:v3`
8. **Build Image** - `docker build -t feed-formulation-be:v3 .`
9. **Run Container** - `docker run -d --name feed-formulation-be -p 8000:8000 --env-file .env feed-formulation-be:v3`
10. **Verify** - `docker ps`

## Features

- ✅ **SSH Key Authentication** - Secure connection using SSH keys with passphrase support
- ✅ **GitHub Authentication** - Automatic git pull with credentials
- ✅ **Real-time Output** - See command execution in real-time
- ✅ **Error Handling** - Stops on first error
- ✅ **Rollback Capability** - Automatically rolls back on failure
- ✅ **Logging** - Saves detailed logs to file
- ✅ **Health Checks** - Verifies deployment success
- ✅ **Dry Run Mode** - Preview commands before execution

## Error Handling

If any step fails:
1. The script stops immediately
2. Automatically attempts rollback of completed steps
3. Logs all errors and rollback attempts
4. Exits with error code 1

## Log Files

Deployment logs are automatically saved to:
- `deployment_log_YYYYMMDD_HHMMSS.log` (timestamped)
- Or custom file if specified with `--log-file`

## Troubleshooting

### SSH Connection Issues
- Verify SSH key exists at `~/.ssh/id_rsa`
- Test SSH connection manually: `ssh ubuntu@47.128.1.51`
- Check key permissions: `chmod 600 ~/.ssh/id_rsa`

### Docker Issues
- Ensure Docker is running on the server
- Check if `jenkins` user has Docker permissions
- Verify `.env` file exists in project directory

### Git Issues
- Ensure repository is up to date
- Check if `v3.0` branch exists
- Verify Git credentials are configured

## Security Notes

- SSH keys should have proper permissions (600)
- Never commit SSH keys to version control
- Use environment variables for sensitive data
- Regularly rotate SSH keys

## Support

For issues or questions:
1. Check the deployment log file
2. Verify server connectivity
3. Test individual commands manually
4. Contact system administrator
