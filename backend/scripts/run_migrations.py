#!/usr/bin/env python3
"""
Migration Runner Script
Executes SQL migration files against the database using existing connection settings.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from app.dependencies import SQLALCHEMY_DATABASE_URL

def read_sql_file(file_path):
    """Read SQL file content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}")
        return None

def clean_sql_content(sql_content):
    """Clean SQL content by removing comments and empty lines."""
    lines = sql_content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        # Skip empty lines
        if not stripped_line:
            continue
        # Skip comment lines
        if stripped_line.startswith('--'):
            continue
        # Skip multi-line comment blocks
        if stripped_line.startswith('/*') or stripped_line.endswith('*/'):
            continue
        
        # Keep original line (with indentation) for PostgreSQL functions
        cleaned_lines.append(line.rstrip())
    
    return '\n'.join(cleaned_lines)

def execute_migration(engine, sql_content, migration_name):
    """Execute a migration SQL content."""
    try:
        print(f"🚀 Executing {migration_name}...")
        
        # Clean the SQL content first
        cleaned_sql = clean_sql_content(sql_content)
        
        # Split SQL content by semicolon, but handle PostgreSQL functions properly
        statements = []
        current_statement = ""
        in_function = False
        
        for line in cleaned_sql.split('\n'):
            current_statement += line + '\n'
            
            # Check if we're entering a function definition
            if 'CREATE OR REPLACE FUNCTION' in line.upper() or 'CREATE FUNCTION' in line.upper():
                in_function = True
            
            # Check if we're ending a function definition
            if in_function and line.strip().startswith('$$ language'):
                in_function = False
                statements.append(current_statement.strip())
                current_statement = ""
                continue
            
            # Regular statement ending
            if not in_function and line.strip().endswith(';'):
                statements.append(current_statement.strip())
                current_statement = ""
        
        # Add any remaining statement
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        # Filter out COMMIT and empty statements
        executable_statements = []
        for stmt in statements:
            if stmt.upper().startswith('COMMIT'):
                continue
            if not stmt or stmt.isspace():
                continue
            executable_statements.append(stmt)
        
        with engine.connect() as connection:
            trans = connection.begin()
            try:
                for i, statement in enumerate(executable_statements):
                    print(f"   📝 Executing statement {i+1}/{len(executable_statements)}...")
                    print(f"       {statement[:50]}..." if len(statement) > 50 else f"       {statement}")
                    connection.execute(text(statement))
                
                trans.commit()
                print(f"✅ {migration_name} completed successfully!")
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error in {migration_name}: {e}")
                print(f"   Statement: {statement[:100]}...")
                print(f"   Rolling back transaction...")
                return False
                
    except Exception as e:
        print(f"❌ Connection error for {migration_name}: {e}")
        return False

def main():
    """Main migration runner."""
    print("🗃️  Feed Formulation - Database Migration Runner")
    print("=" * 50)
    
    # Get database URL from existing configuration
    try:
        database_url = SQLALCHEMY_DATABASE_URL
        print(f"📡 Database URL: {database_url.split('@')[1] if '@' in database_url else 'Unknown'}")
    except Exception as e:
        print(f"❌ Error getting database URL: {e}")
        return False
    
    # Create database engine
    try:
        engine = create_engine(database_url)
        print("🔌 Database connection established")
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return False
    
    # Test connection
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"📊 PostgreSQL Version: {version.split(',')[0]}")
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False
    
    # Define migration files in order
    migrations_dir = Path("migrations")
    migration_files = [
        ("001_user_auth_migration.sql", "Schema Migration - User Authentication"),
        ("002_populate_countries.sql", "Data Migration - Populate Countries")
    ]
    
    # Check if migration files exist
    for filename, description in migration_files:
        file_path = migrations_dir / filename
        if not file_path.exists():
            print(f"❌ Migration file not found: {file_path}")
            return False
    
    # Execute migrations in order
    print("\n🔄 Starting Migration Process...")
    print("-" * 30)
    
    for filename, description in migration_files:
        file_path = migrations_dir / filename
        
        print(f"\n📄 {description}")
        print(f"   File: {filename}")
        
        # Read migration file
        sql_content = read_sql_file(file_path)
        if sql_content is None:
            print(f"❌ Failed to read {filename}")
            return False
        
        # Execute migration
        success = execute_migration(engine, sql_content, filename)
        if not success:
            print(f"❌ Migration failed at {filename}")
            print("   Stopping migration process.")
            return False
    
    print("\n" + "=" * 50)
    print("🎉 All migrations completed successfully!")
    print("\n📋 Next Steps:")
    print("   1. Verify tables were created: SELECT * FROM COUNTRY LIMIT 5;")
    print("   2. Check user_information structure: \\d user_information")
    print("   3. Update your existing user data with country_id values")
    print("   4. Update SQLAlchemy models and API endpoints")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 