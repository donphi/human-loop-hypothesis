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

# Copy the current directory contents into the container at /app
COPY extract_urls.py /app/
COPY publications.txt /app/
COPY download_pdfs.py /app/
COPY extracted_urls.txt /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the python script
# It should be possible to pass arguments like --max-concurrent via docker run
CMD ["python", "download_pdfs.py", "extracted_urls.txt"]