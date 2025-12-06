#!/bin/bash
set -e

echo "=== Setting up Universal Website Scraper ==="

# Check Python version
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
python -m playwright install chromium
python -m playwright install-deps

# Run the server
echo "=== Starting server on http://localhost:8000 ==="
echo "Open http://localhost:8000 in your browser"
echo "Press Ctrl+C to stop the server"
echo ""
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload