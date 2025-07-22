#!/bin/bash

# Purchase Order Status Column Type Fix Script
# This script runs the Python migration to fix the column type mismatch

echo "🚀 Purchase Order Status Column Fix"
echo "===================================="

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
echo "🏃 Running status column type fix..."
python fix_purchase_order_status_column.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Column type fix completed successfully!"
    echo "🎯 Purchase order creation should now work correctly."
    echo "📝 The status column now uses purchaseorderstatus ENUM type."
else
    echo "❌ Column type fix failed!"
    echo "🔧 Please check the error messages above and try again."
    exit 1
fi