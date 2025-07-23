#!/usr/bin/env python3
"""
Migration script to create GRN tables
"""

import os
import sys
import asyncio
import asyncpg
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def run_grn_migration():
    """Run the migration to create GRN tables"""
    
    # Database connection details from environment
    db_config = {
        'host': os.getenv('POSTGRES_HOST', '35.223.185.37'),
        'port': int(os.getenv('POSTGRES_PORT', '5432')),
        'database': os.getenv('POSTGRES_DB', 'postgres'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'root123')
    }
    
    print(f"Connecting to database: {db_config['database']} at {db_config['host']}:{db_config['port']}")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(**db_config)
        print("✅ Connected to database successfully")
        
        # Read migration file
        migration_file = Path(__file__).parent / '003_create_grn_tables_simple.sql'
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print("📄 Running GRN table creation migration...")
        
        # Split the migration into individual statements and execute them
        statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
        
        for i, statement in enumerate(statements):
            if statement:
                try:
                    print(f"  Executing statement {i+1}/{len(statements)}...")
                    await conn.execute(statement)
                except Exception as e:
                    if "already exists" in str(e):
                        print(f"    ⚠️  Skipped (already exists): {str(e)[:100]}...")
                    else:
                        print(f"    ❌ Error: {e}")
                        raise
        
        print("✅ GRN migration completed successfully!")
        
        # Verify tables exist
        result = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('grns', 'grn_items', 'grn_status_history')
            ORDER BY table_name
        """)
        
        print("\n📊 Verified tables:")
        for row in result:
            print(f"  - {row['table_name']}")
        
        # Check GRN table columns
        result = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'grns'
            ORDER BY ordinal_position
        """)
        
        print(f"\n📋 GRN table has {len(result)} columns:")
        for row in result[:5]:  # Show first 5 columns
            print(f"  - {row['column_name']}: {row['data_type']}")
        if len(result) > 5:
            print(f"  ... and {len(result) - 5} more columns")
        
        await conn.close()
        print("\n🎉 GRN migration completed and verified!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_grn_migration())