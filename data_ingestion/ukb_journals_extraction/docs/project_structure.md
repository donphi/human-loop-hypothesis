# Project Structure and Files

This document explains the purpose and functionality of each file in the UK Biobank Journals Extraction project.

## Core Files

### `extract_urls.py`

This script extracts URLs and metadata from the `publications.txt` file and saves them to `extracted_urls.txt`, maintaining an index of processed publications to avoid duplicate downloads.

**Functionality:**
- Reads the `publications.txt` file which contains journal metadata including URLs
- Maintains an index of already processed publications to avoid duplicates
- Only extracts URLs for new publications when run multiple times
- Extracts URLs along with meaningful metadata (publication ID, DOI, first author, shortened title)
- Processes the metadata to create clean, filename-friendly text
- Writes the extracted data to `extracted_urls.txt` in a structured format
- Provides comprehensive error handling and reporting
- Generates statistics by file type and publication year

**Command-line Options:**
- `--input FILE`: Input file containing publication data (default: publications.txt)
- `--output FILE`: Output file for extracted URLs (default: extracted_urls.txt)
- `--metadata FILE`: Output file for detailed metadata (default: metadata.json)
- `--no-append`: Process all publications, not just new ones
- `--filter-year YEAR`: Only process publications from this year or later

**Usage:**
```bash
python extract_urls.py
```

### `kill_downloads.py`

This utility script identifies and terminates any running download processes from previous runs.

**Functionality:**
- Finds Python processes running download_pdfs.py
- Finds Docker containers running the download process
- Safely terminates identified processes
- Provides a dry-run option to preview what would be killed
- Handles both graceful termination and forced killing if needed

**Usage:**
```bash
# Kill all Python download processes
python kill_downloads.py

# Preview what would be killed without actually killing
python kill_downloads.py --dry-run

# Also kill Docker containers running the download process
python kill_downloads.py --include-docker
```

### `download_pdfs.py`

This script downloads files from the URLs in `extracted_urls.txt` with advanced features for reliability, monitoring, content verification, and intelligent organization.

**Functionality:**
- **Multi-format Support**: Handles various file types (PDF, HTML, XML, DOC, TXT)
- **Content Verification**: Validates that downloaded files contain actual, useful content
- **Intelligent Organization**: Sorts files into directories by file type
- **Meaningful Filenames**: Creates filenames based on DOI, author, and title metadata
- **Resumable Downloads**: Keeps track of already downloaded URLs to resume if interrupted
- **Rate Limiting**: Controls the number of concurrent downloads and adds delays between requests
- **Progress Tracking**: Shows download progress for individual files and overall process
- **Comprehensive Logging**: Records all activities, errors, and statistics
- **Failure Handling**: Logs failed downloads separately for later analysis
- **Statistics Reporting**: Provides detailed summary of the download process with file type breakdowns

**Key Features:**
- **Resumable Downloads**: Uses a state file to track downloaded URLs
- **Rate Limiting**: Configurable concurrent downloads and delays
- **Content Verification**: Can check if URLs point to PDFs before downloading
- **Detailed Logging**: Maintains logs of all activities and errors
- **Statistics**: Tracks and reports comprehensive download statistics
- **Progress Visualization**: Shows progress bars for large downloads and overall process

**Usage:**
```bash
python download_pdfs.py extracted_urls.txt [options]
```

**Options:**
- `--max-concurrent N`: Maximum number of concurrent downloads (default: 5)
- `--delay N`: Delay between downloads in seconds (default: 1.0)
- `--download-dir PATH`: Directory to save downloaded PDFs
- `--state-file PATH`: File to store download state
- `--logs-dir PATH`: Directory to store log files
- `--check-content-type`: Check if URL points to a PDF before downloading

### `publications.txt`

This file contains metadata about academic journals from the UK Biobank, including:
- Publication IDs
- Titles
- Keywords
- Authors
- Journal names
- Publication dates
- Abstracts
- URLs to the full papers
- Citation information

This file must be downloaded from the UK Biobank website:
1. Visit https://biobank.ndph.ox.ac.uk/ukb/schema.cgi?id=19 (Schema 19)
2. Download the tab-separated file
3. Place it in the root directory of this project as `publications.txt`

The file is periodically updated with new publications, so it should be re-downloaded occasionally to get the latest papers.

### `extracted_urls.txt`

This file contains the URLs and metadata extracted from `Journals.txt`. Each line has the format:

```
publication_id|doi|first_author|shortened_title|url
```

This structured format allows the download script to create meaningful filenames based on the paper's metadata.

## Docker Files

### `Dockerfile`

Defines the Docker container configuration for the project:
- Uses Python 3.9 as the base image
- Sets up the working directory
- Installs required dependencies
- Copies the necessary files into the container
- Configures the default command to run the download script

## Output Directories

### `data/`

Base directory for all downloaded files, with subdirectories for each file type:

- **`data/pdf/`**: PDF files
- **`data/html/`**: HTML files
- **`data/xml/`**: XML files
- **`data/doc/`**: Word documents
- **`data/txt/`**: Text files
- **`data/unknown/`**: Files with unrecognized formats

These directories are created automatically by the download script.

### `logs/`

Directory containing all log files:
- `download.log`: General log of all download activities
- `failed_downloads.log`: Specific log of failed downloads with error details
- `content_verification.log`: Log of content verification results
- `download_stats.json`: JSON file with download statistics
- `verification_results.json`: Detailed results of content verification for each file

## State and Metadata Files

### `download_state.json`

JSON file that keeps track of already downloaded URLs. This allows the download process to be resumed if interrupted.

### `metadata.json`

JSON file containing comprehensive metadata for each URL, including publication details, authors, DOI, and other information extracted from the publications.txt file. This metadata is used for creating meaningful filenames and organizing the downloaded files.

### `index/publications_index.json`

JSON file that maintains an index of all processed publications. This index is used to:
- Track which publications have already been processed
- Avoid duplicate downloads when the publications.txt file is updated
- Store key metadata for each publication (year, author, title, etc.)
- Enable filtering by year or other criteria

The index is automatically updated each time `extract_urls.py` is run, adding only new publications that weren't previously processed.
