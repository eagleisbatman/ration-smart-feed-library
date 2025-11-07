"""
Minimal AWS Service Stub for MCP Server Fork
AWS S3 integration is not needed for MCP server, so this provides minimal stubs
"""

class AWSService:
    """Stub AWS Service class - not used in MCP fork"""
    
    def upload_pdf_to_s3(self, pdf_data: bytes, user_id: str, report_id: str):
        """
        Stub for PDF upload - not needed for MCP server
        Returns success=False for MCP fork
        """
        return False, None, "PDF upload disabled for MCP server fork"
    
    def upload_bulk_import_log_to_s3(self, log_content: str, filename: str):
        """Stub for bulk import log upload"""
        return False, None, "AWS upload disabled for MCP server fork"
    
    def upload_export_to_s3(self, file_bytes: bytes, admin_user_id: str, filename: str, file_type: str):
        """Stub for export upload"""
        return False, None, "AWS upload disabled for MCP server fork"
    
    def get_latest_bulk_import_log(self):
        """Stub for getting latest log"""
        return False, None, None, None, None, None
    
    def delete_old_export_files(self, file_prefix: str):
        """Stub for deleting old files"""
        return False, "AWS operations disabled", 0

# Create singleton instance
aws_service = AWSService()

