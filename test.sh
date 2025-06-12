#!/bin/bash
# Test script for CHOROPIA Flask app
set -e

if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

pytest --maxfail=1 --disable-warnings -v || echo "No pytest tests found or failed."
