#!/usr/bin/env bash
# Render build script — builds frontend + installs backend deps
set -o errexit  # exit on error

echo "=== Building Frontend ==="
cd frontend
npm install
npm run build
cd ..

echo "=== Installing Backend Dependencies ==="
cd backend
pip install -r requirements.txt
cd ..

echo "=== Build Complete ==="
echo "Frontend dist: $(ls -la frontend/dist/ 2>/dev/null | head -5)"
