#!/usr/bin/env bash
# CostSherlock environment setup

set -euo pipefail

python -m venv venv
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

echo "Setup complete. Activate with: source venv/Scripts/activate"
