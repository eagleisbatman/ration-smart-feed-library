#!/usr/bin/env python3
"""
Bulk Import Logger
Generates detailed text logs for bulk import operations
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Tuple
from middleware.logging_config import get_logger

logger = get_logger("bulk_import_logger")

class BulkImportLogger:
    """Handles generation of detailed bulk import logs"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        
    def start_logging(self):
        """Start timing the bulk import operation"""
        self.start_time = datetime.now()
        logger.info("Bulk import logging started")
    
    def stop_logging(self):
        """Stop timing the bulk import operation"""
        self.end_time = datetime.now()
        logger.info("Bulk import logging stopped")
    
    def get_execution_time(self) -> str:
        """Get formatted execution time"""
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            return f"{duration.total_seconds():.2f} seconds"
        return "Unknown"
    
    def generate_log_content(
        self,
        total_records: int,
        successful_uploads: int,
        failed_uploads: int,
        existing_records: int,
        updated_records: int,
        failed_records: List[Dict[str, Any]]
    ) -> str:
        """
        Generate comprehensive log content for bulk import operation
        
        Args:
            total_records: Total number of records processed
            successful_uploads: Number of successful uploads
            failed_uploads: Number of failed uploads
            existing_records: Number of existing records skipped
            failed_records: List of failed records with details
            
        Returns:
            Formatted log content as string
        """
        log_lines = []
        
        # Header
        log_lines.append("=" * 80)
        log_lines.append("BULK IMPORT OPERATION LOG")
        log_lines.append("=" * 80)
        log_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_lines.append("")
        
        # Summary Section
        log_lines.append("SUMMARY")
        log_lines.append("-" * 40)
        log_lines.append(f"Total Records Processed: {total_records}")
        log_lines.append(f"Successful Uploads: {successful_uploads}")
        log_lines.append(f"Failed Uploads: {failed_uploads}")
        log_lines.append(f"Existing Records (Skipped): {existing_records}")
        log_lines.append(f"Updated Records: {updated_records}")
        log_lines.append(f"Execution Time: {self.get_execution_time()}")
        log_lines.append("")
        
        # Success Rate
        if total_records > 0:
            success_rate = (successful_uploads / total_records) * 100
            log_lines.append(f"Success Rate: {success_rate:.2f}%")
        else:
            log_lines.append("Success Rate: N/A (No records processed)")
        log_lines.append("")
        
        # Failed Records Section
        if failed_records:
            log_lines.append("FAILED RECORDS DETAILS")
            log_lines.append("-" * 40)
            log_lines.append("")
            
            for i, failed_record in enumerate(failed_records, 1):
                log_lines.append(f"Failed Record #{i}")
                log_lines.append(f"  Row Number: {failed_record.get('row', 'Unknown')}")
                log_lines.append(f"  Reason: {failed_record.get('reason', 'Unknown error')}")
                log_lines.append(f"  Data: {failed_record.get('data', {})}")
                log_lines.append("")
        else:
            log_lines.append("FAILED RECORDS DETAILS")
            log_lines.append("-" * 40)
            log_lines.append("No failed records - All records processed successfully!")
            log_lines.append("")
        
        # Correction Suggestions Section
        log_lines.append("CORRECTION SUGGESTIONS")
        log_lines.append("-" * 40)
        log_lines.append("")
        
        # Analyze failure patterns and provide suggestions
        suggestions = self._generate_correction_suggestions(failed_records)
        for suggestion in suggestions:
            log_lines.append(f"• {suggestion}")
        
        if not suggestions:
            log_lines.append("No correction suggestions needed - All records processed successfully!")
        
        log_lines.append("")
        log_lines.append("=" * 80)
        log_lines.append("END OF LOG")
        log_lines.append("=" * 80)
        
        return "\n".join(log_lines)
    
    def _generate_correction_suggestions(self, failed_records: List[Dict[str, Any]]) -> List[str]:
        """
        Generate correction suggestions based on failure patterns
        
        Args:
            failed_records: List of failed records with details
            
        Returns:
            List of correction suggestions
        """
        suggestions = []
        
        if not failed_records:
            return suggestions
        
        # Analyze failure reasons
        missing_fields_count = 0
        country_not_found_count = 0
        feed_type_not_found_count = 0
        feed_category_not_found_count = 0
        invalid_relationship_count = 0
        duplicate_count = 0
        
        for record in failed_records:
            reason = record.get('reason', '').lower()
            if 'missing mandatory fields' in reason:
                missing_fields_count += 1
            elif 'country not found' in reason:
                country_not_found_count += 1
            elif 'feed type not found' in reason:
                feed_type_not_found_count += 1
            elif 'feed category not found' in reason:
                feed_category_not_found_count += 1
            elif 'invalid relationship' in reason or 'category does not belong to type' in reason:
                invalid_relationship_count += 1
            elif 'already exists' in reason or 'duplicate' in reason:
                duplicate_count += 1
        
        # Generate suggestions based on patterns
        if missing_fields_count > 0:
            suggestions.append(f"Missing mandatory fields detected in {missing_fields_count} records. Ensure all required columns (fd_name, fd_category, fd_type, fd_country_name) have values.")
        
        if country_not_found_count > 0:
            suggestions.append(f"Country not found in {country_not_found_count} records. Verify country names exist in the countries table and are spelled correctly.")
        
        if feed_type_not_found_count > 0:
            suggestions.append(f"Feed type not found in {feed_type_not_found_count} records. Ensure feed types exist in the feed_types table and are active.")
        
        if feed_category_not_found_count > 0:
            suggestions.append(f"Feed category not found in {feed_category_not_found_count} records. Ensure feed categories exist in the feed_categories table and are active.")
        
        if invalid_relationship_count > 0:
            suggestions.append(f"Invalid type-category relationship in {invalid_relationship_count} records. Ensure the feed category belongs to the specified feed type.")
        
        if duplicate_count > 0:
            suggestions.append(f"Duplicate records detected in {duplicate_count} records. Check for existing feeds with the same combination of name, type, category, and country.")
        
        # General suggestions
        if len(failed_records) > 0:
            suggestions.append("Review the failed records above and correct the data before re-uploading.")
            suggestions.append("Ensure all reference data (countries, feed types, feed categories) are properly set up in the system.")
            suggestions.append("Check for typos in country names, feed types, and feed categories.")
        
        return suggestions
    
    def save_log_to_file(self, log_content: str, filename: str) -> str:
        """
        Save log content to a file
        
        Args:
            log_content: The log content to save
            filename: The filename to save to
            
        Returns:
            Path to the saved file
        """
        try:
            # Create logs directory if it doesn't exist
            logs_dir = "logs"
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            
            file_path = os.path.join(logs_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            logger.info(f"Bulk import log saved to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to save bulk import log: {str(e)}")
            raise
    
    def generate_filename(self) -> str:
        """
        Generate filename for bulk import log
        
        Returns:
            Filename in format: bulk_import_dd:mm:yy:hh:mm.txt
        """
        now = datetime.now()
        return f"bulk_import_{now.strftime('%d:%m:%y:%H:%M')}.txt"
