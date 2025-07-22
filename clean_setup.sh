#!/bin/bash

# Clean Purchase Order Setup Script
# ⚠️  WARNING: This will DELETE ALL existing purchase order data!

echo "🚀 Clean Purchase Order Schema Setup"
echo "===================================="
echo "⚠️  WARNING: This will DELETE ALL existing purchase order data!"
echo "💀 All purchase orders and their items will be permanently removed!"
echo "🔄 The status column will be recreated with the correct type."
echo ""

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

# Run the clean setup
echo "🏃 Running clean purchase order setup..."
echo "📝 This will:"
echo "   1. Delete all existing purchase order data"
echo "   2. Create purchaseorderstatus ENUM"
echo "   3. Recreate status column with correct type"
echo "   4. Verify the setup"
echo ""

python clean_purchase_order_setup.py

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Clean setup completed successfully!"
    echo "🎯 Purchase order creation will now work correctly."
    echo "📝 All old data has been cleared and schema is properly configured."
    echo "🆕 You can now create purchase orders without any errors."
else
    echo "❌ Clean setup failed!"
    echo "🔧 Please check the error messages above and try again."
    exit 1
fi