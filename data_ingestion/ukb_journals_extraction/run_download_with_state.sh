#!/bin/bash

# This script runs the Docker container with the download_state.json file mounted as a volume
# to ensure that the download state is persisted between runs, preventing duplicate processing.

# Create the download_state.json file if it doesn't exist
if [ ! -f "download_state.json" ]; then
    echo "Creating empty download_state.json file..."
    echo "[]" > download_state.json
fi

# Run the Docker container with all necessary volumes mounted
docker run -v "$(pwd)/data:/app/data" \
           -v "$(pwd)/logs:/app/logs" \
           -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" \
           -v "$(pwd)/index:/app/index" \
           -v "$(pwd)/download_state.json:/app/download_state.json" \
           ukb-journals-extraction python download_pdfs.py extracted_urls.txt

echo "Download process completed with state persistence."