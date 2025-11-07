# AWS S3 Setup for PDF Report Storage

## Environment Variables Required

Add the following environment variables to your `.env` file:

```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key_here
AWS_REGION=us-east-1
AWS_S3_BUCKET=your_s3_bucket_name_here
```

## AWS S3 Bucket Setup

1. **Create S3 Bucket**: Create a new S3 bucket in your AWS account
2. **Configure Permissions**: Ensure the bucket allows uploads from your application
3. **CORS Configuration** (if needed for web access):
   ```json
   [
       {
           "AllowedHeaders": ["*"],
           "AllowedMethods": ["GET", "PUT", "POST"],
           "AllowedOrigins": ["*"],
           "ExposeHeaders": []
       }
   ]
   ```

## File Organization

PDF reports are stored in the following structure:
```
reports/
├── {user_id}/
│   ├── rec-abc123_20240115.pdf
│   ├── rec-def456_20240116.pdf
│   └── eval-ghi789_20240117.pdf
```

## API Endpoints

### POST `/save-report-to-bucket/`

**Request Body:**
```json
{
    "report_id": "rec-abc123",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Report successfully saved to bucket",
    "bucket_url": "https://your-bucket.s3.us-east-1.amazonaws.com/reports/550e8400-e29b-41d4-a716-446655440000/rec-abc123_20240115.pdf"
}
```

## Testing AWS Connection

You can test the AWS connection by calling the test function:

```python
from aws_service import aws_service

success, message = aws_service.test_s3_connection()
print(f"Connection test: {success} - {message}")
```

## Error Handling

The system handles various AWS errors:
- **NoCredentialsError**: AWS credentials not found
- **ClientError**: S3-specific errors (bucket not found, access denied, etc.)
- **General exceptions**: Network issues, timeouts, etc.

All errors are logged and appropriate HTTP status codes are returned.
