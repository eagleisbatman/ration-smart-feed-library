# Cron Job Setup for Report Cleanup

## Overview

The `cleanup_old_reports.py` script automatically deletes reports that are:
- Older than 5 hours
- Not saved to AWS bucket (`saved_to_bucket = false`)
- Still have PDF data in the database

## Cron Job Setup

### Option 1: System Cron (Recommended)

1. **Open crontab editor:**
   ```bash
   crontab -e
   ```

2. **Add the following line to run every 3 hours:**
   ```bash
   # Run cleanup script every 3 hours
   0 */3 * * * cd /path/to/feed-formulation-be && /path/to/venv/bin/python cleanup_old_reports.py >> /path/to/feed-formulation-be/logs/cleanup.log 2>&1
   ```

3. **Example with actual paths:**
   ```bash
   # Run cleanup script every 3 hours
   0 */3 * * * cd /Users/satishchandra/ucdapp/feed-formulation-be && /Users/satishchandra/ucdapp/feed-formulation-be/.venv/bin/python cleanup_old_reports.py >> /Users/satishchandra/ucdapp/feed-formulation-be/logs/cleanup.log 2>&1
   ```

### Option 2: Using systemd (Linux)

1. **Create service file** `/etc/systemd/system/report-cleanup.service`:
   ```ini
   [Unit]
   Description=Report Cleanup Service
   After=network.target

   [Service]
   Type=oneshot
   User=your-user
   WorkingDirectory=/path/to/feed-formulation-be
   ExecStart=/path/to/venv/bin/python cleanup_old_reports.py
   Environment=PATH=/path/to/venv/bin

   [Install]
   WantedBy=multi-user.target
   ```

2. **Create timer file** `/etc/systemd/system/report-cleanup.timer`:
   ```ini
   [Unit]
   Description=Run Report Cleanup every 3 hours
   Requires=report-cleanup.service

   [Timer]
   OnCalendar=*-*-* 00/03:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

3. **Enable and start the timer:**
   ```bash
   sudo systemctl enable report-cleanup.timer
   sudo systemctl start report-cleanup.timer
   ```

## Manual Testing

Test the cleanup script manually:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run cleanup script
python cleanup_old_reports.py

# Check logs
tail -f logs/cleanup.log
```

## Cron Schedule Explanation

- `0 */3 * * *` means:
  - `0` - At minute 0
  - `*/3` - Every 3rd hour
  - `* * *` - Every day, every month, every day of week

So it runs at: 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00

## Monitoring

1. **Check cron logs:**
   ```bash
   tail -f logs/cleanup.log
   ```

2. **Check if cron is running:**
   ```bash
   crontab -l
   ```

3. **Test cron job:**
   ```bash
   # Create a test report and wait 5+ hours
   # Then check if it gets cleaned up
   ```

## Troubleshooting

1. **Script not running:**
   - Check if cron service is running: `sudo service cron status`
   - Verify paths in crontab entry
   - Check file permissions

2. **Permission issues:**
   - Ensure the user running cron has access to the project directory
   - Check database connection permissions

3. **Database connection issues:**
   - Verify `.env` file is accessible
   - Check database credentials and connectivity

## Log Files

The cleanup script logs to:
- `logs/cleanup.log` - Cron output
- `logs/` - Application logs (via logging_config.py)

## Safety Features

The cleanup script includes:
- **Logging**: All operations are logged
- **Error handling**: Exceptions are caught and logged
- **Transaction safety**: Database operations use transactions
- **Selective deletion**: Only deletes reports meeting specific criteria
