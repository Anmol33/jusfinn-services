#!/bin/bash

# Purchase Order ENUM Migration Script
# This script runs the Python migration to add the missing purchaseorderstatus ENUM

echo "🚀 Purchase Order Database Migration"
echo "====================================="

# Check if Python virtual environment exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
else
    echo "⚠️  No virtual environment found. Using system Python..."
fi

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python -c "import sqlalchemy, asyncpg" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing required packages. Installing..."
    pip install sqlalchemy asyncpg
fi

# Run the migration
echo "🏃 Running migration..."
python migrate_purchase_order_enum.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully!"
    echo "🎯 Purchase order creation should now work correctly."
else
    echo "❌ Migration failed!"
    echo "🔧 Please check the error messages above and try again."
    exit 1
fi