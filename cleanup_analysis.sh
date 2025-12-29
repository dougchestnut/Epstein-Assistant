#!/bin/bash

# Directory to search
SEARCH_DIR="./epstein_files"

if [ ! -d "$SEARCH_DIR" ]; then
    echo "Directory $SEARCH_DIR does not exist."
    exit 1
fi

echo "Scanning for analysis.json files missing 'is_photo' field..."

# Find and process files
find -L "$SEARCH_DIR" -name "analysis.json" -type f | while read -r file; do
    if ! grep -q '"is_photo"' "$file"; then
        echo "Removing incomplete analysis: $file"
        rm "$file"
    fi
done

echo "Cleanup complete."
