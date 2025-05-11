# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
# Install necessary libraries
RUN pip install requests

# Copy the current directory contents into the container at /app
COPY extract_urls.py /app/
COPY Journals.txt /app/
COPY download_pdfs.py /app/
COPY extracted_urls.txt /app/

# Run the python script
# It should be possible to pass arguments like --max-concurrent via docker run
CMD ["python", "download_pdfs.py", "extracted_urls.txt"]