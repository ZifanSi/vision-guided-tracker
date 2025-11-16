#!/usr/bin/env sh

# Navigate to the same directory as this script
cd "$(dirname "$0")"
flask run --host=0.0.0.0 -p 80