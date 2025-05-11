# Beginner's Guide to UK Biobank Journal Extraction

This guide explains the UK Biobank Journal Extraction process in simple terms for users who are new to programming or data processing. We'll walk through what this project does, why it's useful, and how to use it step by step.

## What Does This Project Do?

This project helps you download academic papers (PDFs) from a list of URLs. It's specifically designed for downloading papers related to the UK Biobank, which is a large-scale biomedical database containing health information from half a million UK participants.

The process works in two main steps:
1. Extract URLs from a list of journals
2. Download the PDFs from those URLs

## Why Is This Useful?

Researchers often need to analyze many academic papers to conduct literature reviews or meta-analyses. Downloading hundreds or thousands of papers manually would be extremely time-consuming. This tool automates the process, making it much faster and more reliable.

## The Files and What They Do

### Main Files

- **publications.txt**: A list of academic journals with their metadata (titles, authors, URLs, etc.)
- **extracted_urls.txt**: A list of URLs with metadata (DOI, author, title) extracted from publications.txt
- **extract_urls.py**: A program that extracts URLs and metadata from publications.txt
- **download_pdfs.py**: A program that downloads files, verifies their content, and organizes them by file type
- **kill_downloads.py**: A utility to stop any running download processes
- **metadata.json**: A file containing detailed information about each journal article

### Output Files and Folders

- **data/**: Main folder for downloaded files, with subfolders for different file types:
  - **data/pdf/**: PDF files
  - **data/html/**: HTML files
  - **data/xml/**: XML files
  - **data/doc/**: Word documents
  - **data/txt/**: Text files
  - **data/unknown/**: Files with unrecognized formats
- **logs/**: Folder containing information about the download process
  - **download.log**: Record of all download activities
  - **failed_downloads.log**: List of URLs that couldn't be downloaded
  - **content_verification.log**: Information about the quality of downloaded files
  - **download_stats.json**: Statistics about the download process
  - **verification_results.json**: Detailed information about each downloaded file

## Step-by-Step Instructions

### Step 1: Make Sure You Have Everything You Need

You need either:
- Docker installed on your computer (easiest option)
- OR Python installed with the required packages

This guide focuses on using Docker because it's simpler for beginners.

### Step 2: Getting the Publications Data

Before you can use this system, you need to download the latest publications data from the UK Biobank website:

1. Visit https://biobank.ndph.ox.ac.uk/ukb/schema.cgi?id=19 (Schema 19)
2. Download the tab-separated file
3. Save it in the project folder as `publications.txt`

This file contains information about all academic papers related to the UK Biobank, including their URLs.

When you want to update your collection with new publications:
1. Download the latest publications.txt file from the same URL
2. Replace your existing publications.txt file with the new one
3. Run the extract_urls.py script again - it will automatically identify and process only the new publications

### Step 3: Understanding How the System Works

The project uses an intelligent index system to:
- Keep track of which publications have already been processed
- Only download new publications when you update the publications.txt file
- Organize files by type and create meaningful filenames
- Verify that downloaded content is valid and useful

### Step 3: Building the Docker Container

A Docker container is like a pre-packaged environment that has everything needed to run the programs.

1. Open a terminal or command prompt
2. Navigate to the project folder
3. Type this command and press Enter:

```bash
docker build -t ukb-journals-extraction .
```

This might take a minute or two. When it's done, you'll see a message indicating success.

### Step 4: Running the Programs

The process involves two main steps that must be executed in order:

#### Step 4.1: Extract URLs and Metadata

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

You can also use additional options:
- To process only publications from a specific year or later:
  ```bash
  docker run -v "$(pwd)/publications.txt:/app/publications.txt" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python extract_urls.py --filter-year 2020
  ```

- To process all publications, ignoring the index:
  ```bash
  docker run -v "$(pwd)/publications.txt:/app/publications.txt" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python extract_urls.py --no-append
  ```

#### Step 4.2: Download Files

After extracting the URLs, you can run the download process:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
```

#### What These Commands Do:

- The first command extracts URLs and metadata from publications.txt
- The second command downloads the files and organizes them
- Creates folders on your computer:
  - `data`: Where the files will be saved (organized by file type)
  - `logs`: Where information about the download process will be saved
- Uses the default settings (5 downloads at a time, 1-second delay between downloads)

**Important**: You must run the extract_urls.py script first to generate the extracted_urls.txt file before running the download_pdfs.py script.

### Step 5: Monitoring the Download Process

While the program is running, you'll see messages in the terminal showing its progress. These messages tell you:
- Which URLs are being downloaded
- Whether each download succeeded or failed
- Overall progress of the download process

### Step 6: What to Do If You Need to Stop

If you need to stop the download process before it's finished:

1. Press `Ctrl+C` in the terminal
2. The program will save its progress before stopping

If downloads are still running in the background or you need to force-stop all download processes:

```bash
python kill_downloads.py
```

This utility will find and terminate any running download processes.

### Step 7: Resuming Downloads Later

If you stopped the download process and want to continue later:

1. Open a terminal or command prompt
2. Navigate to the project folder
3. Run the same command as in Step 4:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
```

The program will automatically skip files that were already downloaded and continue with the remaining ones.

### Step 8: Checking the Results

After the download process is complete (or even while it's running), you can:

1. Look in the `data` folder to see the downloaded files:
   - Files are organized into subfolders by type (pdf, html, xml, etc.)
   - Each file has a meaningful name based on:
     - The DOI (Digital Object Identifier) of the paper
     - The first author's last name
     - A shortened version of the paper's title
   - The system has verified that each file contains actual content (not just error pages or redirects)
2. Look in the `logs` folder to see information about the download process:
   - `download.log`: Detailed record of all activities
   - `failed_downloads.log`: List of URLs that couldn't be downloaded
   - `download_stats.json`: Statistics about the download process

## Customizing the Download Process

If you want to change how the download process works, you can add options to the command:

### Download Fewer Files at Once

If your internet connection is slow, you might want to download fewer files at once:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt --max-concurrent 2
```

This sets the maximum number of concurrent downloads to 2 (default is 5).

### Add More Delay Between Downloads

If websites are blocking you for downloading too quickly, you can add more delay:

```bash
docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt --delay 3
```

This adds a 3-second delay between downloads (default is 1 second).

## What Makes This System Special

This system does more than just download files:

1. **Smart File Organization**: Files are sorted by type (PDF, HTML, etc.) into separate folders
2. **Content Verification**: The system checks that each file contains actual, useful content
3. **Quality Control**: It identifies and flags redirects, error pages, and empty documents
4. **Comprehensive Logging**: Detailed information is saved about each download and any issues
5. **Intelligent Naming**: Files are named in a way that makes them easy to identify and organize

## Common Problems and Solutions

### "No such file or directory"

This usually means one of the required files is missing or in the wrong location. Make sure:
- You're in the correct project folder
- The files `publications.txt`, `extracted_urls.txt`, `extract_urls.py`, and `download_pdfs.py` exist

### Downloads Keep Failing

If many downloads are failing, it could be because:
- Your internet connection is unstable
- The websites are blocking automated downloads
- The URLs in extracted_urls.txt are no longer valid

Try:
- Using a more stable internet connection
- Adding more delay between downloads (see "Add More Delay Between Downloads" above)
- Checking a few URLs manually in your web browser to see if they still work

### Docker Command Not Found

If you get a message saying "docker: command not found", it means Docker is not installed or not in your PATH. Make sure:
- You've installed Docker correctly
- Docker is running
- You've opened a new terminal after installing Docker

## Getting Help

If you're still having trouble:
1. Check the logs in the `logs` folder for error messages
2. Look for specific error messages in the terminal output
3. Consult the more detailed documentation in the `docs` folder