# 📚 UK Biobank Journals Extraction

This module is part of the Human-in-the-Loop for Automated Hypothesis Testing in Biobank Research project. It handles the extraction and downloading of academic journal PDFs related to UK Biobank research.

---

## 🎯 Module Purpose

This module automates the process of:
1. Extracting URLs from a list of UK Biobank-related journal references
2. Tracking which publications have already been processed to avoid duplicates
3. Downloading only new publications when the source file is updated
4. Downloading the corresponding files in a reliable, resumable manner
5. Tracking download statistics and handling failures gracefully

The goal is to build and maintain a comprehensive corpus of UK Biobank research papers for further analysis, embedding generation, and hypothesis testing.

---

## 🛠️ Key Features

- **Incremental Updates**: Only processes new publications when you update the source file
- **Multi-format Support**: Handles various file types (PDF, HTML, XML, DOC, TXT)
- **Content Verification**: Validates that downloaded files contain actual, useful content
- **Intelligent Organization**: Sorts files into directories by file type
- **Content Quality Assurance**: Identifies and flags redirects, error pages, and empty documents
- **Intelligent Filename Generation**: Creates meaningful filenames using DOI, author, and title
- **Metadata Extraction**: Extracts not just URLs but also publication metadata
- **Resumable Downloads**: Continues from where it left off if interrupted
- **Rate Limiting**: Prevents overloading servers with configurable concurrency and delays
- **Comprehensive Logging**: Detailed logs of all activities and failures
- **Progress Tracking**: Real-time progress visualization for individual and overall downloads
- **Statistics Reporting**: Detailed summary of download process with file type breakdowns
- **Docker Integration**: Containerized for consistent execution across environments
- **Filtering Capabilities**: Can filter publications by year or other criteria

---

## 📁 File Structure

```bash
.
├── Dockerfile                # Docker container configuration
├── publications.txt          # Source data with journal metadata (must be downloaded)
├── README.md                 # This file
├── download_pdfs.py          # Script to download PDFs from URLs
├── extract_urls.py           # Script to extract URLs from journal data
├── extracted_urls.txt        # Extracted URLs ready for downloading
├── kill_downloads.py         # Utility to terminate running download processes
├── index/                    # Directory for tracking processed publications
│   └── publications_index.json # Index of processed publications
├── docs/                     # Documentation
│   ├── beginners_guide.md    # Simplified guide for new users
│   ├── docker_guide.md       # Instructions for using Docker
│   └── project_structure.md  # Explanation of project files and structure
├── data/                     # Base directory for downloaded files (created automatically)
│   ├── pdf/                  # PDF files
│   ├── html/                 # HTML files
│   ├── xml/                  # XML files
│   ├── doc/                  # Word documents
│   ├── txt/                  # Text files
│   └── unknown/              # Files with unrecognized formats
└── logs/                     # Directory for logs (created automatically)
    ├── download.log          # General log of all activities
    ├── failed_downloads.log  # Log of failed downloads with error details
    ├── content_verification.log # Log of content verification results
    ├── download_stats.json   # Statistics about the download process
    └── verification_results.json # Detailed content verification results
```

---

## 🚀 Getting Started

### Prerequisites

- Docker (recommended)
- OR Python 3.6+ with required packages:
  - requests
  - tqdm

### Obtaining the Publications Data

Before using this system, you need to download the latest publications data:

1. Visit https://biobank.ndph.ox.ac.uk/ukb/schema.cgi?id=19 (Schema 19)
2. Download the tab-separated file
3. Save it in the project folder as `publications.txt`

This file contains information about all academic papers related to the UK Biobank, including their URLs.

### Quick Start with Docker

1. Build the Docker image:
   ```bash
   docker build -t ukb-journals-extraction .
   ```

2. Extract URLs and metadata:
   ```bash
   # First, make sure the directories exist
   mkdir -p index
   
   # Run the extraction script
   docker run -v "$(pwd)/publications.txt:/app/publications.txt" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python extract_urls.py
   ```

3. Download files:
   ```bash
   docker run -v "$(pwd)/data:/app/data" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/extracted_urls.txt:/app/extracted_urls.txt" -v "$(pwd)/index:/app/index" ukb-journals-extraction python download_pdfs.py extracted_urls.txt
   ```

**Important**: You must run the extract_urls.py script first to generate the extracted_urls.txt file before running the download_pdfs.py script.

### Updating with New Publications

When you want to update your collection with new publications:

1. Download the latest publications.txt file from the UK Biobank website
2. Replace your existing publications.txt file with the new one
3. Run the extract_urls.py script again - it will automatically identify and process only the new publications
4. Run the download_pdfs.py script to download the newly extracted URLs

### Running Directly with Python

1. Install required packages:
   ```bash
   pip install requests tqdm python-magic PyPDF2 beautifulsoup4
   ```

2. Extract URLs and metadata:
   ```bash
   python extract_urls.py
   ```

3. Run the download script:
   ```bash
   python download_pdfs.py extracted_urls.txt
   ```

**Note**: The extraction step must be completed before running the download script.

### Filtering Options

The extract_urls.py script supports several filtering options:

```bash
# Only process publications from 2020 or later
python extract_urls.py --filter-year 2020

# Process all publications, ignoring the index
python extract_urls.py --no-append

# Specify custom input and output files
python extract_urls.py --input custom_publications.txt --output custom_urls.txt --metadata custom_metadata.json
```

### Customizing the Download Process

```bash
python download_pdfs.py extracted_urls.txt --max-concurrent 3 --delay 2 --check-content-type
```

Options:
- `--max-concurrent N`: Maximum number of concurrent downloads (default: 5)
- `--delay N`: Delay between downloads in seconds (default: 1.0)
- `--check-content-type`: Check if URL points to a PDF before downloading
- `--download-dir PATH`: Directory to save downloaded PDFs
- `--logs-dir PATH`: Directory to store log files

---

## 📊 Monitoring and Results

- Check download progress in real-time in the terminal
- View detailed logs in the `logs/` directory
- Access downloaded files in the `data/` directory, organized by file type
- Review download statistics in `logs/download_stats.json`

---

## 📝 Documentation

Detailed documentation is available in the `docs/` directory:

- [Project Structure](docs/project_structure.md): Explanation of all files and their purpose
- [Docker Guide](docs/docker_guide.md): Comprehensive guide to using Docker with this project
- [Beginner's Guide](docs/beginners_guide.md): Simplified instructions for new users

---

## 🔄 Integration with Main Project

This module is part of the larger Human-in-the-Loop for Automated Hypothesis Testing in Biobank Research project. The PDFs downloaded by this module serve as input for:

1. The embedding generation module, which creates vector representations of the papers
2. The knowledge graph module, which extracts relationships between phenotypes and diseases
3. The RAG pipeline, which uses the papers for retrieval-augmented generation

---

## 🧪 Future Improvements

- Implement automatic retry mechanism for failed downloads
- Add support for more document formats
- Implement more sophisticated rate limiting based on domains
- Integrate with citation management systems
- Add OCR capabilities for scanned documents
- Implement automatic alternative source finding for failed downloads
- Add full-text extraction for all document types