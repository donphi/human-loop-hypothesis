# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install necessary libraries
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install requests tqdm python-magic PyPDF2 beautifulsoup4

# Create directories for downloads, logs, and index
RUN mkdir -p /app/data/pdf /app/data/html /app/data/xml /app/data/doc /app/data/txt /app/data/unknown /app/logs /app/index

# Copy the necessary scripts into the container at /app
COPY extract_urls.py /app/
COPY publications.txt /app/
COPY download_pdfs.py /app/
# Don't copy extracted_urls.txt as it should be mounted as a volume

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create an empty download state file to avoid errors if not mounted
RUN echo "[]" > /app/download_state.json

# Run the python script
# IMPORTANT: When running the container, mount these volumes to prevent duplicate data:
# -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt"
# -v "$(pwd)/download_state.json:/app/download_state.json"
# -v "$(pwd)/index:/app/index"
# Example: docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/download_state.json:/app/download_state.json" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
CMD ["python", "download_pdfs.py", "extracted_urls.txt"]