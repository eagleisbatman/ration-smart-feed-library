"""
Database Sync Verification Script
Checks if database is in sync with latest migrations
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.dependencies import get_db

def check_table_exists(db: Session, table_name: str) -> bool:
    """Check if a table exists"""
    query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = :table_name
        )
    """)
    result = db.execute(query, {"table_name": table_name})
    return result.scalar()

def check_column_exists(db: Session, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = :table_name 
            AND column_name = :column_name
        )
    """)
    result = db.execute(query, {"table_name": table_name, "column_name": column_name})
    return result.scalar()

def check_feed_count(db: Session, country_name: str) -> int:
    """Check feed count for a country"""
    query = text("SELECT COUNT(*) FROM feeds WHERE fd_country_name = :country_name")
    result = db.execute(query, {"country_name": country_name})
    return result.scalar() or 0

def verify_database_sync():
    """Verify database is in sync with latest migrations"""
    db = next(get_db())
    
    print("=" * 60)
    print("DATABASE SYNC VERIFICATION")
    print("=" * 60)
    print()
    
    checks = {
        "Core Tables": [
            ("feed_translations", check_table_exists(db, "feed_translations")),
            ("country_languages", check_table_exists(db, "country_languages")),
            ("feeds", check_table_exists(db, "feeds")),
            ("countries", check_table_exists(db, "countries")),
            ("users", check_table_exists(db, "users") or check_table_exists(db, "user_information")),
        ],
        "Multi-Tenant Tables (Migration 033)": [
            ("organizations", check_table_exists(db, "organizations")),
            ("api_keys", check_table_exists(db, "api_keys")),
            ("api_usage", check_table_exists(db, "api_usage")),
        ],
        "OTP & Admin Support (Migration 034)": [
            ("otp_codes", check_table_exists(db, "otp_codes")),
            ("users.is_superadmin", check_column_exists(db, "users", "is_superadmin") or check_column_exists(db, "user_information", "is_superadmin")),
            ("users.country_admin_country_id", check_column_exists(db, "users", "country_admin_country_id") or check_column_exists(db, "user_information", "country_admin_country_id")),
            ("users.organization_admin_org_id", check_column_exists(db, "users", "organization_admin_org_id") or check_column_exists(db, "user_information", "organization_admin_org_id")),
        ],
        "Regional Variations (Migration 035)": [
            ("feed_regional_variations", check_table_exists(db, "feed_regional_variations")),
        ],
        "Feed Data": [
            ("Ethiopia feeds", check_feed_count(db, "Ethiopia")),
            ("Vietnam feeds", check_feed_count(db, "Vietnam")),
        ],
    }
    
    all_passed = True
    missing_items = []
    
    for category, items in checks.items():
        print(f"\n{category}:")
        print("-" * 60)
        for name, exists in items:
            status = "✅" if exists else "❌"
            if isinstance(exists, bool):
                value = "EXISTS" if exists else "MISSING"
            else:
                value = f"{exists} records"
            
            print(f"  {status} {name:40} {value}")
            
            if not exists:
                all_passed = False
                missing_items.append((category, name))
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ DATABASE IS FULLY SYNCED")
        print("=" * 60)
    else:
        print("⚠️  DATABASE NEEDS MIGRATIONS")
        print("=" * 60)
        print("\nMissing items:")
        for category, name in missing_items:
            print(f"  - {category}: {name}")
        print("\nTo fix:")
        print("  1. Run missing migrations:")
        print("     railway connect postgres")
        print("     # Then run SQL from backend/migrations/")
        print("  2. See DATABASE_SYNC_VERIFICATION.md for details")
    
    db.close()
    return all_passed

if __name__ == "__main__":
    try:
        verify_database_sync()
    except Exception as e:
        print(f"Error verifying database: {str(e)}")
        sys.exit(1)

