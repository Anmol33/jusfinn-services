#!/usr/bin/env python3
"""
Quick migration script to add missing columns to purchase_order_items table
"""

import os
import sys
import asyncio
import asyncpg
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def run_migration():
    """Run the migration to add missing columns"""
    
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
        migration_file = Path(__file__).parent / '002_add_missing_po_columns.sql'
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        print("📄 Running migration script...")
        
        # Execute migration
        await conn.execute(migration_sql)
        
        print("✅ Migration completed successfully!")
        
        # Verify columns exist
        result = await conn.fetch("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'purchase_order_items' 
            AND column_name IN ('received_quantity', 'pending_quantity')
            ORDER BY column_name
        """)
        
        print("\n📊 Verified columns:")
        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']} (default: {row['column_default']})")
        
        await conn.close()
        print("\n🎉 Migration completed and verified!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_migration())