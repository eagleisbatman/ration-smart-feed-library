#!/usr/bin/env python3
"""
Cleanup Script for Old Reports
Deletes reports older than 5 hours that haven't been saved to AWS bucket

This script is designed to be run via cron job every 3 hours.
Usage: python cleanup_old_reports.py
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.dependencies import SQLALCHEMY_DATABASE_URL
from middleware.logging_config import get_logger

# Setup logging
logger = get_logger("cleanup_old_reports")

def cleanup_old_reports():
    """
    Delete reports older than 5 hours that haven't been saved to AWS bucket
    """
    try:
        # Create database engine and session
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Calculate cutoff time (5 hours ago)
        cutoff_time = datetime.utcnow() - timedelta(hours=5)
        
        logger.info(f"Starting cleanup of reports older than: {cutoff_time}")
        
        # Find reports to delete
        # Criteria: 
        # 1. Created more than 5 hours ago
        # 2. Not saved to bucket (saved_to_bucket = false)
        # 3. Have PDF data (report is not null)
        
        query = text("""
            SELECT id, report_id, user_id, created_at, saved_to_bucket 
            FROM reports 
            WHERE created_at < :cutoff_time 
            AND saved_to_bucket = false 
            AND report IS NOT NULL
        """)
        
        result = db.execute(query, {"cutoff_time": cutoff_time})
        reports_to_delete = result.fetchall()
        
        if not reports_to_delete:
            logger.info("No old reports found to delete")
            return
        
        logger.info(f"Found {len(reports_to_delete)} old reports to delete")
        
        # Log the reports that will be deleted
        for report in reports_to_delete:
            logger.info(f"Will delete report: ID={report.id}, Report_ID={report.report_id}, User_ID={report.user_id}, Created={report.created_at}")
        
        # Delete the old reports
        delete_query = text("""
            DELETE FROM reports 
            WHERE created_at < :cutoff_time 
            AND saved_to_bucket = false 
            AND report IS NOT NULL
        """)
        
        result = db.execute(delete_query, {"cutoff_time": cutoff_time})
        deleted_count = result.rowcount
        
        db.commit()
        
        logger.info(f"Successfully deleted {deleted_count} old reports")
        
        # Log summary
        logger.info(f"Cleanup completed: {deleted_count} reports deleted")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise
    finally:
        if 'db' in locals():
            db.close()

def main():
    """
    Main function to run the cleanup
    """
    try:
        logger.info("Starting report cleanup process")
        cleanup_old_reports()
        logger.info("Report cleanup process completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Report cleanup process failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
