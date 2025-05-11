# Docker Guide

This guide explains how to use Docker with the UK Biobank Journals Extraction project. It's designed to be accessible for users with limited Docker experience.

## What is Docker?

Docker is a platform that allows you to package and run applications in isolated environments called "containers." Think of a container as a lightweight, standalone package that includes everything needed to run the application: code, runtime, system tools, libraries, and settings.

## Why Use Docker for This Project?

1. **Consistency**: Docker ensures the application runs the same way on any system
2. **Isolation**: The application runs in its own environment without affecting your system
3. **Simplicity**: You don't need to install Python or any dependencies on your system
4. **Persistence**: Downloaded files and logs are saved even when the container stops

## Prerequisites

1. Install Docker on your system:
   - [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
   - [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
   - [Docker for Linux](https://docs.docker.com/engine/install/)

2. Make sure Docker is running on your system (you should see the Docker icon in your system tray or menu bar)

## Preparing the Data

Before using this system, you need to download the latest publications data from the UK Biobank website:

1. Visit https://biobank.ndph.ox.ac.uk/ukb/schema.cgi?id=19 (Schema 19)
2. Download the tab-separated file
3. Save it in the project folder as `publications.txt`

This file contains information about all academic papers related to the UK Biobank, including their URLs.

When you want to update your collection with new publications:
1. Download the latest publications.txt file from the same URL
2. Replace your existing publications.txt file with the new one
3. Run the extract_urls.py script again - it will automatically identify and process only the new publications

## Step-by-Step Guide

### 1. Building the Docker Image

First, you need to build the Docker image. This creates a template that will be used to run the container.

1. Open a terminal or command prompt
2. Navigate to the project directory (where the Dockerfile is located)
3. Run the following command:

```bash
docker build -t ukb-journals-extraction .
```

This command builds a Docker image named "ukb-journals-extraction" based on the instructions in the Dockerfile.

### 2. Running the Container

The process involves two main steps that must be executed in order:

#### Step 1: Extract URLs and Metadata

First, you need to extract URLs and metadata from the publications.txt file:

```bash
# First, make sure the directories exist
mkdir -p index

# Run the extraction script
docker run -v "$(pwd)/publications.txt:/app/publications.txt" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python extract_urls.py
```

This command will:
- Read the publications.txt file
- Check which publications are new (not in the index)
- Extract URLs and metadata only for new publications
- Update the index with the newly processed publications
- Save the extracted data to extracted_urls.txt
- Generate a metadata.json file with comprehensive information

You can also use additional options:
- To process only publications from a specific year or later:
  ```bash
  docker run -v "$(pwd)/publications.txt:/app/publications.txt" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python extract_urls.py --filter-year 2020
  ```

- To process all publications, ignoring the index:
  ```bash
  docker run -v "$(pwd)/publications.txt:/app/publications.txt" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python extract_urls.py --no-append
  ```

#### Step 2: Download Files

After extracting the URLs, you can run the download process:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
```

#### Explanation:

- `docker run`: Command to start a new container
- `-v "$(pwd)/data:/app/data"`: Maps the data folder from your computer to the container (will contain subfolders for different file types)
- `-v "$(pwd)/metadata.json:/app/metadata.json"`: Maps the metadata file for persistent storage
- `-v "$(pwd)/logs:/app/logs"`: Maps the logs folder from your computer to the container
- `ukb-journals-extraction`: The name of the image to run

This command will start the download process using the default settings.

### 3. Running with Custom Options

You can customize the download process by passing options to the scripts:

#### For extract_urls.py:

```bash
docker run -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/metadata.json:/app/metadata.json" ukb-journals-extraction python extract_urls.py --input Journals.txt --output extracted_urls.txt
```

#### For download_pdfs.py:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt --max-concurrent 3 --delay 2
```

This example sets the maximum concurrent downloads to 3 and adds a 2-second delay between downloads.

#### Available Options:

- `--max-concurrent N`: Maximum number of concurrent downloads (default: 5)
- `--delay N`: Delay between downloads in seconds (default: 1.0)
- `--check-content-type`: Check content type before downloading
- `--verify-content`: Verify that downloaded content is valid and useful (enabled by default)

### 4. Stopping the Container

If you need to stop the download process:

1. Open a new terminal or command prompt
2. Run `docker ps` to see the running containers
3. Find the container ID for the ukb-journals-extraction container
4. Run `docker stop [CONTAINER_ID]`

The download process will save its state, so you can resume it later.

If you need to forcefully terminate all download processes (including those running in the background):

```bash
python kill_downloads.py --include-docker
```

This utility will find and stop all download processes and containers.

### 5. Resuming Downloads

To resume the download process after stopping it:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
```

The script will automatically skip files that have already been downloaded.

### 6. Viewing Logs

You can view the logs in the `logs` directory:

- `download.log`: General log of all download activities
- `failed_downloads.log`: Specific log of failed downloads with error details
- `content_verification.log`: Log of content verification results
- `download_stats.json`: JSON file with download statistics
- `verification_results.json`: Detailed results of content verification for each file

### 7. Accessing Downloaded Files

All downloaded files will be available in the `data` directory on your computer, organized into subdirectories by file type:

- `data/pdf/`: PDF files
- `data/html/`: HTML files
- `data/xml/`: XML files
- `data/doc/`: Word documents
- `data/txt/`: Text files
- `data/unknown/`: Files with unrecognized formats

## Troubleshooting

### Container Exits Immediately

If the container exits immediately after starting:

1. Check the logs in the `logs` directory
2. Make sure the `extracted_urls.txt` file exists and contains URLs
3. Try running with the `-it` flag to see the output directly:

```bash
docker run -it -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
```

### Permission Issues

If you encounter permission issues with the mapped volumes:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" --user "$(id -u):$(id -g)" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
```

This runs the container with your user ID, which should resolve permission issues.

### No Space Left on Device

If you receive a "no space left on device" error:

1. Check your disk space
2. Clean up unused Docker resources:

```bash
docker system prune
```

This removes unused containers, networks, and images.