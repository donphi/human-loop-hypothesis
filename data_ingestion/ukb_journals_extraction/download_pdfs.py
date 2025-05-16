import requests
import os
import json
import argparse
import concurrent.futures
import atexit
import time
import logging
import re
import hashlib
import mimetypes
import magic  # python-magic library for file type detection
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
from tqdm import tqdm
from bs4 import BeautifulSoup  # For HTML content analysis
import PyPDF2  # For PDF content verification

# Configuration constants
STATE_FILE = '/app/download_state.json'
BASE_DIR = '/app/data'
LOGS_DIR = '/app/logs'
FAILED_DOWNLOADS_LOG = os.path.join(LOGS_DIR, 'failed_downloads.log')
SCIHUB_ATTEMPTS_LOG = os.path.join(LOGS_DIR, 'scihub_attempts.log')
STATS_FILE = os.path.join(LOGS_DIR, 'download_stats.json')
CONTENT_VERIFICATION_LOG = os.path.join(LOGS_DIR, 'content_verification.log')
DEFAULT_RATE_LIMIT = 5  # Default max concurrent downloads
DEFAULT_DELAY = 1.0  # Default delay between downloads in seconds
MIN_PDF_SIZE = 10 * 1024  # Minimum size for a valid PDF (10KB)
MIN_TEXT_CONTENT = 1000  # Minimum number of characters for valid text content
DEFAULT_SCIHUB_RATE_LIMIT_DELAY = 5  # Default delay between Sci-Hub requests in seconds

# File type directories
FILE_TYPE_DIRS = {
    'pdf': os.path.join(BASE_DIR, 'pdf'),
    'sci_pdf': os.path.join(BASE_DIR, 'sci_pdf')
}

# Create a logs directory within sci_pdf for Sci-Hub specific logs
SCIHUB_LOGS_DIR = os.path.join(FILE_TYPE_DIRS['sci_pdf'], 'logs')

# Global variables
downloaded_urls = set()
failed_urls = set()
scihub_attempted_urls = set()
verification_results = {}
start_time = None
stats = {
    'total_urls': 0,
    'attempted_downloads': 0,
    'successful_downloads': 0,
    'failed_downloads': 0,
    'skipped_downloads': 0,
    'scihub_attempts': 0,
    'scihub_successes': 0,
    'scihub_failures': 0,
    'start_time': None,
    'end_time': None,
    'elapsed_time': None,
    'last_run_date': None,
    'file_types': {},
    'verification': {
        'valid_content': 0,
        'invalid_content': 0,
        'unverified': 0
    }
}

# Sci-Hub domains to try
SCIHUB_DOMAINS = []

# Set up logging
def setup_logging():
    """Set up logging configuration."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(SCIHUB_LOGS_DIR, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(LOGS_DIR, 'download.log')),
            logging.StreamHandler()
        ]
    )
    
    # Create a separate logger for failed downloads
    failed_logger = logging.getLogger('failed_downloads')
    failed_logger.setLevel(logging.ERROR)
    failed_handler = logging.FileHandler(FAILED_DOWNLOADS_LOG)
    failed_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    failed_logger.addHandler(failed_handler)
    
    # Create a separate logger for Sci-Hub attempts
    scihub_logger = logging.getLogger('scihub_attempts')
    scihub_logger.setLevel(logging.INFO)
    scihub_handler = logging.FileHandler(SCIHUB_ATTEMPTS_LOG)
    scihub_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    scihub_logger.addHandler(scihub_handler)
    
    # Create a separate logger for content verification
    verification_logger = logging.getLogger('content_verification')
    verification_logger.setLevel(logging.INFO)
    verification_handler = logging.FileHandler(CONTENT_VERIFICATION_LOG)
    verification_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    verification_logger.addHandler(verification_handler)
    
    return failed_logger, scihub_logger, verification_logger

# Load and save state functions
def load_state():
    """Loads the set of downloaded URLs from the state file."""
    global downloaded_urls
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                downloaded_urls = set(json.load(f))
            logging.info(f"Loaded {len(downloaded_urls)} previously downloaded URLs from state file.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading state file {STATE_FILE}: {e}")
            downloaded_urls = set()  # Start fresh if state file is corrupt

def save_state():
    """Saves the set of downloaded URLs to the state file."""
    if downloaded_urls:
        try:
            # Ensure the directory for the state file exists
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(list(downloaded_urls), f)
            logging.info(f"Saved {len(downloaded_urls)} downloaded URLs to state file.")
        except IOError as e:
            logging.error(f"Error saving state file {STATE_FILE}: {e}")

def load_stats():
    """Loads the statistics from the stats file."""
    global stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
            logging.info(f"Loaded statistics from {STATS_FILE}.")
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Error loading stats file {STATS_FILE}: {e}")
            # Keep default stats if file is corrupt

def save_stats():
    """Saves the statistics to the stats file."""
    try:
        # Ensure the directory for the stats file exists
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        
        # Update end time and elapsed time
        if stats['start_time']:
            stats['end_time'] = datetime.now().isoformat()
            start_dt = datetime.fromisoformat(stats['start_time'])
            end_dt = datetime.fromisoformat(stats['end_time'])
            elapsed = end_dt - start_dt
            stats['elapsed_time'] = str(elapsed)
        
        stats['last_run_date'] = datetime.now().isoformat()
        
        # Add verification results
        stats['verification_results'] = verification_results
        
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
        logging.info(f"Saved statistics to {STATS_FILE}.")
    except IOError as e:
        logging.error(f"Error saving stats file {STATS_FILE}: {e}")

def save_verification_results():
    """Saves the verification results to a separate file."""
    try:
        verification_file = os.path.join(LOGS_DIR, 'verification_results.json')
        with open(verification_file, 'w') as f:
            json.dump(verification_results, f, indent=2)
        logging.info(f"Saved verification results to {verification_file}.")
    except IOError as e:
        logging.error(f"Error saving verification results: {e}")

# Register functions to be called on script exit
atexit.register(save_state)
atexit.register(save_stats)
atexit.register(save_verification_results)

def detect_content_type(response):
    """Detect the content type from the response headers and content."""
    # Always return 'pdf' since we're only handling PDFs now
    return 'pdf'

def verify_pdf_content(filepath, verification_logger):
    """Verify that a PDF file contains actual content and is not just a redirect or empty file."""
    try:
        # Check file size
        file_size = os.path.getsize(filepath)
        if file_size < MIN_PDF_SIZE:
            verification_logger.info(f"PDF too small ({file_size} bytes): {filepath}")
            return False, f"File too small: {file_size} bytes"
        
        # Try to read the PDF
        try:
            with open(filepath, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                num_pages = len(pdf_reader.pages)
                
                if num_pages == 0:
                    verification_logger.info(f"PDF has no pages: {filepath}")
                    return False, "PDF has no pages"
                
                # Check if at least one page has text
                has_text = False
                for i in range(min(3, num_pages)):  # Check first 3 pages at most
                    page = pdf_reader.pages[i]
                    text = page.extract_text()
                    if text and len(text) > 100:  # At least 100 characters
                        has_text = True
                        break
                
                if not has_text:
                    verification_logger.info(f"PDF appears to have no text content: {filepath}")
                    return False, "No text content found in first few pages"
                
                verification_logger.info(f"Valid PDF with {num_pages} pages: {filepath}")
                return True, f"Valid PDF with {num_pages} pages"
                
        except Exception as e:
            verification_logger.info(f"Error reading PDF {filepath}: {e}")
            return False, f"Error reading PDF: {e}"
            
    except Exception as e:
        verification_logger.info(f"Error verifying PDF {filepath}: {e}")
        return False, f"Error verifying: {e}"

def normalize_url(url, base_url=None):
    """Ensure URL has a proper scheme and is absolute."""
    if not url:
        return None
        
    # Remove quotes if present
    url = url.strip("'\"")
    
    # Check if it's a relative URL
    if url.startswith('/'):
        if base_url:
            # Parse the base URL to get the scheme and netloc
            parsed_base = urlparse(base_url)
            base = f"{parsed_base.scheme}://{parsed_base.netloc}"
            return urljoin(base, url)
        else:
            # If no base URL is provided, we can't normalize a relative URL
            return None
    
    # Check if URL has a scheme
    if not url.startswith(('http://', 'https://')):
        # Add https:// as default scheme
        return 'https://' + url
        
    return url

def extract_redirect_url(html_content, base_url=None):
    """Extract redirect URL from HTML content if it exists."""
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for redirect meta tags
        meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
        if meta_refresh:
            content_attr = meta_refresh.get('content', '')
            # Extract URL from content attribute (format: "0;URL=http://example.com")
            match = re.search(r'url=([^;]+)', content_attr, re.I)
            if match:
                redirect_url = match.group(1).strip()
                return normalize_url(redirect_url, base_url)
        
        # Check for redirect in query parameters (common in temporary redirect files)
        # Look for elements with 'Redirect' parameter
        redirect_links = soup.find_all('a', href=re.compile(r'Redirect=', re.I))
        if redirect_links:
            for link in redirect_links:
                href = link.get('href', '')
                match = re.search(r'Redirect=([^&]+)', href, re.I)
                if match:
                    # URL decode the redirect parameter
                    import urllib.parse
                    redirect_url = urllib.parse.unquote(match.group(1))
                    return normalize_url(redirect_url, base_url)
        
        # Check for URL in query parameters of the current page
        if 'Redirect=' in html_content:
            match = re.search(r'Redirect=([^&"\'\s]+)', html_content, re.I)
            if match:
                # URL decode the redirect parameter
                import urllib.parse
                redirect_url = urllib.parse.unquote(match.group(1))
                return normalize_url(redirect_url, base_url)
        
        return None
    except Exception as e:
        logging.error(f"Error extracting redirect URL: {e}")
        return None

def verify_content(filepath, file_type, verification_logger):
    """Verify that the downloaded file contains valid, useful content."""
    return verify_pdf_content(filepath, verification_logger)

def download_from_scihub(doi, output_path, scihub_logger, verification_logger, rate_limit_delay=DEFAULT_SCIHUB_RATE_LIMIT_DELAY):
    """Download a paper from Sci-Hub using direct form submission."""
    global stats
    
    if not doi:
        scihub_logger.info(f"No DOI found, cannot use Sci-Hub")
        return False
    
    scihub_logger.info(f"Attempting to download DOI {doi} from Sci-Hub")
    stats['scihub_attempts'] += 1
    
    # Apply rate limiting
    time.sleep(rate_limit_delay)
    
    # Set up session with browser-like headers
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://sci-hub.se',
        'Referer': 'https://sci-hub.se/'
    }
    
    for scihub_url in SCIHUB_DOMAINS:
        try:
            scihub_logger.info(f"Trying Sci-Hub domain: {scihub_url}")
            
            # First get the main page to get any cookies
            main_response = session.get(scihub_url, headers=headers, timeout=10)
            
            if main_response.status_code != 200:
                time.sleep(5)
                scihub_logger.info(f"Failed to access {scihub_url}: {main_response.status_code}")
                continue
            
            scihub_logger.info(f"Successfully accessed {scihub_url}")
            
            # Submit the DOI
            data = {
                'request': doi,
                'sci-hub-plugin-check': ''
            }
            
            response = session.post(scihub_url, data=data, headers=headers, timeout=10)
            
            if response.status_code != 200:
                time.sleep(15)
                scihub_logger.info(f"Failed to submit DOI to {scihub_url}: {response.status_code}")
                continue
            
            scihub_logger.info(f"Successfully submitted DOI to {scihub_url}")
            
            # Save the response HTML for debugging
            debug_path = os.path.join(SCIHUB_LOGS_DIR, f"debug_response_{doi.replace('/', '_')}.html")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            scihub_logger.info(f"Saved response HTML to {debug_path}")
            
            # Parse the response to find the PDF
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the PDF iframe
            iframe = soup.find('iframe')
            if iframe and iframe.get('src'):
                pdf_url = iframe.get('src')
                scihub_logger.info(f"Found PDF URL in iframe: {pdf_url}")
                
                # If the PDF URL is relative, make it absolute
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
                
                # Download the PDF
                scihub_logger.info(f"Downloading PDF from {pdf_url}")
                pdf_response = session.get(pdf_url, headers=headers, stream=True)
                
                if pdf_response.status_code != 200:
                    scihub_logger.info(f"Failed to download PDF: {pdf_response.status_code}")
                    continue
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                
                # Save the PDF
                with open(output_path, 'wb') as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Verify the content
                is_valid, reason = verify_content(output_path, 'sci_pdf', verification_logger)
                
                if is_valid:
                    scihub_logger.info(f"Successfully downloaded PDF to {output_path}")
                    stats['scihub_successes'] += 1
                    return True
                else:
                    scihub_logger.info(f"Downloaded file is not a valid PDF: {reason}")
                    # Try the next method or domain
            
            # If no iframe, look for download links
            download_links = []
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if href.endswith('.pdf') or 'pdf' in href.lower():
                    download_links.append(href)
            
            if download_links:
                pdf_url = download_links[0]
                scihub_logger.info(f"Found PDF download link: {pdf_url}")
                
                # If the PDF URL is relative, make it absolute
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
                
                # Download the PDF
                pdf_response = session.get(pdf_url, headers=headers, stream=True)
                
                if pdf_response.status_code != 200:
                    scihub_logger.info(f"Failed to download PDF: {pdf_response.status_code}")
                    continue
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                
                # Save the PDF
                with open(output_path, 'wb') as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Verify the content
                is_valid, reason = verify_content(output_path, 'sci_pdf', verification_logger)
                
                if is_valid:
                    scihub_logger.info(f"Successfully downloaded PDF to {output_path}")
                    stats['scihub_successes'] += 1
                    return True
                else:
                    scihub_logger.info(f"Downloaded file is not a valid PDF: {reason}")
                    # Try the next method or domain
            
            # If no iframe or download link, look for embed tag within article div
            article_div = soup.find('div', id='article')
            if article_div:
                embed_tag = article_div.find('embed')
                if embed_tag and embed_tag.get('src'):
                    pdf_url = embed_tag.get('src')
                    scihub_logger.info(f"Found PDF URL in embed tag: {pdf_url}")

                    # If the PDF URL is relative, make it absolute
                    if pdf_url.startswith('//'):
                        pdf_url = 'https:' + pdf_url
                    elif not pdf_url.startswith(('http://', 'https://')):
                        pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url

                    # Download the PDF
                    pdf_response = session.get(pdf_url, headers=headers, stream=True)

                    if pdf_response.status_code != 200:
                        scihub_logger.info(f"Failed to download PDF: {pdf_response.status_code}")
                        continue

                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

                    # Save the PDF
                    with open(output_path, 'wb') as f:
                        for chunk in pdf_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    # Verify the content
                    is_valid, reason = verify_content(output_path, 'sci_pdf', verification_logger)
                    
                    if is_valid:
                        scihub_logger.info(f"Successfully downloaded PDF to {output_path}")
                        stats['scihub_successes'] += 1
                        return True
                    else:
                        scihub_logger.info(f"Downloaded file is not a valid PDF: {reason}")
                        # Try the next method or domain

            # If still no PDF found, try to extract from JavaScript
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    pdf_matches = re.findall(r'https?://[^\s\'"]+\.pdf', script.string)
                    if pdf_matches:
                        pdf_url = pdf_matches[0]
                        scihub_logger.info(f"Found PDF URL in script: {pdf_url}")
                        
                        # Download the PDF
                        pdf_response = session.get(pdf_url, headers=headers, stream=True)
                        
                        if pdf_response.status_code != 200:
                            scihub_logger.info(f"Failed to download PDF: {pdf_response.status_code}")
                            continue
                        
                        # Ensure the directory exists
                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        
                        # Save the PDF
                        with open(output_path, 'wb') as f:
                            for chunk in pdf_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # Verify the content
                        is_valid, reason = verify_content(output_path, 'sci_pdf', verification_logger)
                        
                        if is_valid:
                            scihub_logger.info(f"Successfully downloaded PDF to {output_path}")
                            stats['scihub_successes'] += 1
                            return True
                        else:
                            scihub_logger.info(f"Downloaded file is not a valid PDF: {reason}")
                            # Try the next method or domain
            
            scihub_logger.info(f"Could not find PDF on {scihub_url}")
            
        except Exception as e:
            scihub_logger.info(f"Error with {scihub_url}: {e}")
    
    scihub_logger.info("All Sci-Hub domains failed")
    stats['scihub_failures'] += 1
    return False

def download_file(url_info, delay=0, failed_logger=None, scihub_logger=None, verification_logger=None, scihub_delay=DEFAULT_SCIHUB_RATE_LIMIT_DELAY):
    """Downloads a file from the given URL with content verification, falling back to Sci-Hub if needed."""
    global stats, verification_results, downloaded_urls, scihub_attempted_urls
    
    # Parse URL info
    if '|http' in url_info:
        parts = url_info.split('|')
        url = parts[-1]  # The actual URL is the last part
        metadata_parts = parts[:-1]  # All parts except the last one
    else:
        url = url_info
        metadata_parts = None
    
    original_url = url_info
    
    if url_info in downloaded_urls:
        logging.info(f"Skipping {url_info}: already downloaded.")
        stats['skipped_downloads'] += 1
        return False  # Indicate skipped
    
    # Extract DOI and file type from metadata parts
    doi = None
    expected_file_type = None
    
    if metadata_parts and len(metadata_parts) >= 5:
        pub_id, doi, author, title, expected_file_type = metadata_parts
    elif metadata_parts and len(metadata_parts) >= 2:
        doi = metadata_parts[1]
        expected_file_type = metadata_parts[4] if len(metadata_parts) >= 5 else None
    
    # If URL doesn't end with .pdf, doesn't contain 'render' or 'printable', and a DOI is available,
    # go directly to Sci-Hub method
    if doi and not url.lower().endswith('.pdf') and 'render' not in url.lower() and 'printable' not in url.lower():
        logging.info(f"URL {url} is not a direct PDF download. Trying Sci-Hub with DOI {doi}")
        
        # Generate filename for Sci-Hub download
        if metadata_parts and len(metadata_parts) >= 3:
            pub_id, doi_str, author = metadata_parts[:3]
            
            # Try to extract year from the index file
            year = datetime.now().strftime('%Y')  # Default to current year
            
            # Load the index file if it hasn't been loaded yet
            if not hasattr(download_file, 'index_loaded'):
                download_file.index_loaded = True
                download_file.publication_index = {}
                index_file = os.path.join('/app/index', 'publications_index.json')
                if os.path.exists(index_file):
                    try:
                        with open(index_file, 'r') as f:
                            download_file.publication_index = json.load(f)
                        logging.info(f"Loaded {len(download_file.publication_index)} publications from index file.")
                    except Exception as e:
                        logging.error(f"Error loading index file: {e}")
            
            # Try to find the publication in the index to get the year
            for idx_pub_id, pub_data in getattr(download_file, 'publication_index', {}).items():
                if pub_data.get('doi', '') == doi_str or idx_pub_id == pub_id:
                    year = pub_data.get('year', year)
                    break
            
            # Extract SHORT_ID from the DOI
            short_id = doi_str
            if '/' in doi_str:
                # Try to extract the numeric part after the last slash or after parentheses
                doi_parts = doi_str.split('/')[-1]
                # Handle cases like (15)60175-1
                if '(' in doi_parts and ')' in doi_parts:
                    match = re.search(r'\)(\d+(-\d+)?)', doi_parts)
                    if match:
                        short_id = match.group(1)
                else:
                    # Extract numeric parts
                    match = re.search(r'(\d+(-\d+)?)', doi_parts)
                    if match:
                        short_id = match.group(1)
            
            # Create a filename with the format: Year_Author_ShortID.pdf
            filename_base = f"{year}_{author}_{short_id}"
            
            # Clean up filename
            filename_base = filename_base.replace('?', '_').replace('&', '_').replace('=', '_')
            filename_base = filename_base.replace('(', '[').replace(')', ']')
            filename_base = re.sub(r'_+', '_', filename_base)
            
            # Limit the base filename length to avoid path length issues
            max_base_length = 40
            if len(filename_base) > max_base_length:
                filename_base = filename_base[:max_base_length]
                # Remove trailing underscores or punctuation
                filename_base = re.sub(r'[_\-.,;:]+$', '', filename_base)
            
            output_path = os.path.join(FILE_TYPE_DIRS['sci_pdf'], f"{filename_base}.pdf")
        else:
            # Generate a simple filename using the DOI
            doi_cleaned = doi.replace('/', '_').replace('.', '_')
            output_path = os.path.join(FILE_TYPE_DIRS['sci_pdf'], f"scihub_{doi_cleaned}.pdf")
        
        # Attempt Sci-Hub download
        scihub_attempted_urls.add(original_url)
        success = download_from_scihub(doi, output_path, scihub_logger, verification_logger, scihub_delay)
        
        if success:
            downloaded_urls.add(original_url)
            stats['successful_downloads'] += 1
            logging.info(f"Successfully downloaded {url} from Sci-Hub to {output_path}")
            return True  # Indicate success
        else:
            stats['failed_downloads'] += 1
            error_msg = f"Failed to download {url} from Sci-Hub"
            logging.error(error_msg)
            if failed_logger:
                failed_logger.error(f"{original_url} - Failed Sci-Hub download for DOI {doi}")
            failed_urls.add(original_url)
            return False  # Indicate failure
    
    # Apply rate limiting delay if specified
    if delay > 0:
        time.sleep(delay)
    
    # Regular download attempt for PDF, render, or printable URLs
    try:
        # Generate filename and determine file type
        if metadata_parts and len(metadata_parts) >= 5:
            pub_id, doi, author, title, expected_file_type = metadata_parts
            
            # Try to extract year from the index file
            year = datetime.now().strftime('%Y')  # Default to current year
            
            # Load the index file if it hasn't been loaded yet
            if not hasattr(download_file, 'index_loaded'):
                download_file.index_loaded = True
                download_file.publication_index = {}
                index_file = os.path.join('/app/index', 'publications_index.json')
                if os.path.exists(index_file):
                    try:
                        with open(index_file, 'r') as f:
                            download_file.publication_index = json.load(f)
                        logging.info(f"Loaded {len(download_file.publication_index)} publications from index file.")
                    except Exception as e:
                        logging.error(f"Error loading index file: {e}")
            
            # Try to find the publication in the index to get the year
            for idx_pub_id, pub_data in getattr(download_file, 'publication_index', {}).items():
                if pub_data.get('doi', '') == doi or idx_pub_id == pub_id:
                    year = pub_data.get('year', year)
                    break
            
            # Extract SHORT_ID from the DOI
            short_id = doi
            if '/' in doi:
                # Try to extract the numeric part after the last slash or after parentheses
                doi_parts = doi.split('/')[-1]
                # Handle cases like (15)60175-1
                if '(' in doi_parts and ')' in doi_parts:
                    match = re.search(r'\)(\d+(-\d+)?)', doi_parts)
                    if match:
                        short_id = match.group(1)
                else:
                    # Extract numeric parts
                    match = re.search(r'(\d+(-\d+)?)', doi_parts)
                    if match:
                        short_id = match.group(1)
            
            # Create a filename with the format: Year_Author_ShortID.ext
            filename_base = f"{year}_{author}_{short_id}"
        else:
            # For URLs without metadata, try to extract information from the index file
            # Load the index file if it hasn't been loaded yet
            if not hasattr(download_file, 'index_loaded'):
                download_file.index_loaded = True
                download_file.publication_index = {}
                index_file = os.path.join('/app/index', 'publications_index.json')
                if os.path.exists(index_file):
                    try:
                        with open(index_file, 'r') as f:
                            download_file.publication_index = json.load(f)
                        logging.info(f"Loaded {len(download_file.publication_index)} publications from index file.")
                    except Exception as e:
                        logging.error(f"Error loading index file: {e}")
            
            # Try to find the URL in the index
            found_in_index = False
            for pub_id, pub_data in getattr(download_file, 'publication_index', {}).items():
                if pub_data.get('url') == url:
                    # Create a filename with the format: DOI_Author_Title.ext
                    doi = pub_data.get('doi', '')
                    if not doi or len(doi) < 3:
                        doi = pub_id
                    
                    author = pub_data.get('first_author', 'Unknown')
                    title = pub_data.get('title', '')
                    year = pub_data.get('year', '')
                    
                    # Clean up the title for filename use
                    title = re.sub(r'[\\/*?:"<>|#]', '', title)
                    title = re.sub(r'[\s,;]+', '_', title)
                    
                    # Get just a short part of the title (first 15 characters)
                    short_title = title[:15] if title else ''
                    
                    # Extract just the DOI number without the full URL
                    short_doi = doi.split('/')[-1] if doi and '/' in doi else doi
                    if len(short_doi) > 10:
                        short_doi = short_doi[:10]
                    
                    # Create a filename format: Year_Author_ShortID
                    # Extract SHORT_ID from the DOI
                    short_id = short_doi
                    if '/' in doi:
                        # Try to extract the numeric part after the last slash or after parentheses
                        doi_parts = doi.split('/')[-1]
                        # Handle cases like (15)60175-1
                        if '(' in doi_parts and ')' in doi_parts:
                            match = re.search(r'\)(\d+(-\d+)?)', doi_parts)
                            if match:
                                short_id = match.group(1)
                        else:
                            # Extract numeric parts
                            match = re.search(r'(\d+(-\d+)?)', doi_parts)
                            if match:
                                short_id = match.group(1)
                    
                    filename_base = f"{year}_{author}_{short_id}"
                    
                    # Remove any double underscores
                    filename_base = re.sub(r'_+', '_', filename_base)
                    
                    # Ensure the filename is not too long
                    max_filename_length = 40
                    if len(filename_base) > max_filename_length:
                        filename_base = filename_base[:max_filename_length]
                    expected_file_type = pub_data.get('file_type', 'unknown')
                    found_in_index = True
                    break
            
            if not found_in_index:
                # Fall back to extracting filename from URL
                parsed_url = urlparse(url)
                path = parsed_url.path
                filename_from_url = os.path.basename(path)
                
                # Try to extract a DOI-like string from the URL
                doi_match = re.search(r'10\.\d{4,}[\/\\].+?(?=[\/\\&?]|$)', url)
                short_doi = ''
                if doi_match:
                    short_doi = doi_match.group(0).split('/')[-1]
                    if len(short_doi) > 10:
                        short_doi = short_doi[:10]
                else:
                    # Use a hash of the URL as an identifier if no DOI is found
                    short_doi = hashlib.md5(url.encode()).hexdigest()[:10]
                
                # Use current year as fallback
                year = datetime.now().strftime('%Y')
                
                # Use "unknown" as author if not available
                author = "unknown"
                
                # Try to extract a title from the filename
                if filename_from_url and '.' in filename_from_url:
                    title_part = filename_from_url.split('.')[0]
                    # Clean up title
                    title_part = re.sub(r'[\\/*?:"<>|#]', '', title_part)
                    title_part = re.sub(r'[\s,;]+', '_', title_part)
                    short_title = title_part[:15] if title_part else 'untitled'
                else:
                    short_title = 'untitled'
                
                # Create a filename with the format: Year_Author_ShortID
                # Extract SHORT_ID from the DOI or URL
                short_id = short_doi
                if doi_match:
                    doi_parts = doi_match.group(0).split('/')[-1]
                    # Handle cases like (15)60175-1
                    if '(' in doi_parts and ')' in doi_parts:
                        match = re.search(r'\)(\d+(-\d+)?)', doi_parts)
                        if match:
                            short_id = match.group(1)
                    else:
                        # Extract numeric parts
                        match = re.search(r'(\d+(-\d+)?)', doi_parts)
                        if match:
                            short_id = match.group(1)
                
                filename_base = f"{year}_{author}_{short_id}"
                
                # Remove any double underscores
                filename_base = re.sub(r'_+', '_', filename_base)
                
                # Ensure the filename is not too long
                max_filename_length = 40
                if len(filename_base) > max_filename_length:
                    filename_base = filename_base[:max_filename_length]
                
                # Try to guess file type from URL
                expected_file_type = 'pdf'
            
        # Clean up filename
        if not filename_base or len(filename_base) < 5:
            # Generate a filename if not available or invalid
            filename_base = f"downloaded_file_{len(downloaded_urls) + 1}"
        
        # Decode HTML entities if present
        try:
            import html
            filename_base = html.unescape(filename_base)
        except (ImportError, AttributeError):
            # Fallback for basic HTML entities if html module is not available
            filename_base = filename_base.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            filename_base = filename_base.replace('&quot;', '"').replace('&#39;', "'")
            # Handle numeric entities like &#233;
            filename_base = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), filename_base)
        
        # Replace problematic characters in filename
        filename_base = filename_base.replace('?', '_').replace('&', '_').replace('=', '_')
        
        # Handle parentheses in DOIs - replace with square brackets which are safer
        filename_base = filename_base.replace('(', '[').replace(')', ']')
        
        # Remove any duplicate underscores
        filename_base = re.sub(r'_+', '_', filename_base)
        
        # Create directories if they don't exist
        for dir_path in FILE_TYPE_DIRS.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # Temporary filepath for initial download
        # Use a hash of the URL to create a unique but short identifier to avoid path length issues
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        temp_filepath = os.path.join(BASE_DIR, f"temp_{url_hash}")
        
        logging.info(f"Downloading {url} to temporary file...")
        
        # Add browser-like User-Agent for URLs with printable or render parameters
        headers = {}
        if "printable" in url.lower() or "render" in url.lower():
            logging.info(f"Using browser-like User-Agent for URL with printable/render parameter")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        # Allow redirects and set a reasonable timeout
        response = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        
        # Detect actual content type from response
        actual_file_type = detect_content_type(response)
        
        # Update file type statistics
        stats['file_types'][actual_file_type] = stats['file_types'].get(actual_file_type, 0) + 1
        
        # Determine final file extension and path
        ext = '.pdf'  # Always PDF for now
        
        # Ensure filename has the correct extension
        if not filename_base.lower().endswith(ext.lower()):
            filename = filename_base + ext
        else:
            filename = filename_base
        
        # Determine final filepath
        filepath = os.path.join(FILE_TYPE_DIRS['pdf'], filename)
        
        # Download the file with progress bar for large files
        total_size = int(response.headers.get('content-length', 0))
        with open(temp_filepath, 'wb') as f:
            if total_size > 1024*1024:  # Only show progress for files > 1MB
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        # Verify the file was downloaded and is not empty
        if os.path.getsize(temp_filepath) == 0:
            os.remove(temp_filepath)  # Remove empty file
            raise IOError("Downloaded file is empty")
        
        # Verify content quality
        is_valid, reason = verify_content(temp_filepath, actual_file_type, verification_logger)
        
        # Move the file to its final location
        os.rename(temp_filepath, filepath)
        
        # Update verification results
        verification_results[original_url] = {
            'filepath': filepath,
            'expected_type': expected_file_type,
            'actual_type': actual_file_type,
            'is_valid': is_valid,
            'reason': reason,
            'size': os.path.getsize(filepath)
        }
        
        # Update statistics
        if is_valid:
            stats['verification']['valid_content'] += 1
            downloaded_urls.add(original_url)
            stats['successful_downloads'] += 1
            logging.info(f"Successfully downloaded {url} to {filepath}")
            logging.info(f"Content verification: {'VALID' if is_valid else 'INVALID'} - {reason}")
            return True  # Indicate success
        else:
            stats['verification']['invalid_content'] += 1
            # For invalid content, try Sci-Hub if DOI is available
            if doi and doi not in scihub_attempted_urls:
                logging.info(f"Downloaded content is invalid: {reason}. Trying Sci-Hub with DOI {doi}")
                
                # Generate filename for Sci-Hub download
                doi_cleaned = doi.replace('/', '_').replace('.', '_')
                scihub_filepath = os.path.join(FILE_TYPE_DIRS['sci_pdf'], f"{filename_base}.pdf")
                
                # Attempt Sci-Hub download
                scihub_attempted_urls.add(doi)
                success = download_from_scihub(doi, scihub_filepath, scihub_logger, verification_logger, scihub_delay)
                
                if success:
                    downloaded_urls.add(original_url)
                    stats['successful_downloads'] += 1
                    logging.info(f"Successfully downloaded {url} from Sci-Hub to {scihub_filepath}")
                    return True  # Indicate success
            
            # If no DOI or Sci-Hub attempt failed, mark as failed
            stats['failed_downloads'] += 1
            logging.error(f"Downloaded content is invalid and Sci-Hub attempt failed or not possible: {reason}")
            if failed_logger:
                failed_logger.error(f"{original_url} - Invalid content: {reason}")
            failed_urls.add(original_url)
            return False  # Indicate failure
    
    except requests.exceptions.RequestException as e:
        # For printable/render URLs, try curl as a fallback
        if "printable" in url.lower() or "render" in url.lower():
            logging.info(f"Requests download failed for printable/render URL. Trying curl fallback: {url}")
            try:
                import subprocess
                
                # Use curl with browser-like user agent and follow redirects
                curl_cmd = [
                    'curl', '-L',
                    '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    url,
                    '-o', temp_filepath
                ]
                
                # Execute curl command
                subprocess.run(curl_cmd, check=True)
                
                # Verify the file was downloaded and is not empty
                if os.path.getsize(temp_filepath) == 0:
                    os.remove(temp_filepath)  # Remove empty file
                    raise IOError("Downloaded file is empty")
                
                # Verify content quality
                is_valid, reason = verify_content(temp_filepath, 'pdf', verification_logger)
                
                # Move the file to its final location
                os.rename(temp_filepath, filepath)
                
                # Update verification results
                verification_results[original_url] = {
                    'filepath': filepath,
                    'expected_type': expected_file_type,
                    'actual_type': 'pdf',
                    'is_valid': is_valid,
                    'reason': reason,
                    'size': os.path.getsize(filepath),
                    'method': 'curl_fallback'
                }
                
                # Update statistics
                if is_valid:
                    stats['verification']['valid_content'] += 1
                    downloaded_urls.add(original_url)
                    stats['successful_downloads'] += 1
                    logging.info(f"Successfully downloaded {url} to {filepath} using curl fallback")
                    logging.info(f"Content verification: {'VALID' if is_valid else 'INVALID'} - {reason}")
                    return True  # Indicate success
                else:
                    # For invalid content, try Sci-Hub if DOI is available
                    if doi and doi not in scihub_attempted_urls:
                        logging.info(f"Downloaded content is invalid: {reason}. Trying Sci-Hub with DOI {doi}")
                        
                        # Generate filename for Sci-Hub download
                        doi_cleaned = doi.replace('/', '_').replace('.', '_')
                        scihub_filepath = os.path.join(FILE_TYPE_DIRS['sci_pdf'], f"{filename_base}.pdf")
                        
                        # Attempt Sci-Hub download
                        scihub_attempted_urls.add(doi)
                        success = download_from_scihub(doi, scihub_filepath, scihub_logger, verification_logger, scihub_delay)
                        
                        if success:
                            downloaded_urls.add(original_url)
                            stats['successful_downloads'] += 1
                            logging.info(f"Successfully downloaded {url} from Sci-Hub to {scihub_filepath}")
                            return True  # Indicate success
                
            except Exception as curl_e:
                logging.error(f"Curl fallback also failed for {url}: {curl_e}")
                # Continue to the standard failure handling
        
        # If standard download and curl fallback failed, try Sci-Hub if DOI is available
        if doi and doi not in scihub_attempted_urls:
            logging.info(f"Standard download failed: {e}. Trying Sci-Hub with DOI {doi}")
            
            # Generate filename for Sci-Hub download
            doi_cleaned = doi.replace('/', '_').replace('.', '_')
            scihub_filepath = os.path.join(FILE_TYPE_DIRS['sci_pdf'], f"{filename_base if 'filename_base' in locals() else 'scihub_' + doi_cleaned}.pdf")
            
            # Attempt Sci-Hub download
            scihub_attempted_urls.add(doi)
            success = download_from_scihub(doi, scihub_filepath, scihub_logger, verification_logger, scihub_delay)
            
            if success:
                downloaded_urls.add(original_url)
                stats['successful_downloads'] += 1
                logging.info(f"Successfully downloaded {url} from Sci-Hub to {scihub_filepath}")
                return True  # Indicate success
        
        # If all methods failed, mark as failed
        stats['failed_downloads'] += 1
        error_msg = f"Error downloading {url}: {e}"
        logging.error(error_msg)
        if failed_logger:
            failed_logger.error(f"{original_url} - {e}")
        failed_urls.add(original_url)
        return False  # Indicate failure
    
    except Exception as e:
        # If any other error occurs, try Sci-Hub if DOI is available
        if doi and doi not in scihub_attempted_urls:
            logging.info(f"Error processing {url}: {e}. Trying Sci-Hub with DOI {doi}")
            
            # Generate filename for Sci-Hub download
            doi_cleaned = doi.replace('/', '_').replace('.', '_')
            scihub_filepath = os.path.join(FILE_TYPE_DIRS['sci_pdf'], f"{filename_base if 'filename_base' in locals() else 'scihub_' + doi_cleaned}.pdf")
            
            # Attempt Sci-Hub download
            scihub_attempted_urls.add(doi)
            success = download_from_scihub(doi, scihub_filepath, scihub_logger, verification_logger, scihub_delay)
            
            if success:
                downloaded_urls.add(original_url)
                stats['successful_downloads'] += 1
                logging.info(f"Successfully downloaded {url} from Sci-Hub to {scihub_filepath}")
                return True  # Indicate success
        
        # If all methods failed, mark as failed
        stats['failed_downloads'] += 1
        error_msg = f"Unexpected error processing {url}: {e}"
        logging.error(error_msg)
        if failed_logger:
            failed_logger.error(f"{original_url} - {e}")
        failed_urls.add(original_url)
        return False  # Indicate failure

def format_time(seconds):
    """Format seconds into a human-readable time string."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

def print_summary():
    """Print a summary of the download process."""
    if stats['start_time']:
        start_dt = datetime.fromisoformat(stats['start_time'])
        end_dt = datetime.now()
        elapsed = end_dt - start_dt
        elapsed_str = format_time(elapsed.total_seconds())
    else:
        elapsed_str = "Unknown"
    
    logging.info("\n" + "="*50)
    logging.info("DOWNLOAD SUMMARY")
    logging.info("="*50)
    logging.info(f"Total URLs processed: {stats['total_urls']}")
    logging.info(f"Attempted downloads: {stats['attempted_downloads']}")
    logging.info(f"Successfully downloaded: {stats['successful_downloads']}")
    logging.info(f"Failed downloads: {stats['failed_downloads']}")
    logging.info(f"Skipped (previously downloaded): {stats['skipped_downloads']}")
    
    logging.info("\nSci-Hub statistics:")
    logging.info(f"  Attempts: {stats['scihub_attempts']}")
    logging.info(f"  Successes: {stats['scihub_successes']}")
    logging.info(f"  Failures: {stats['scihub_failures']}")
    
    logging.info("\nFile type statistics:")
    for file_type, count in stats['file_types'].items():
        logging.info(f"  {file_type}: {count}")
    
    logging.info("\nContent verification:")
    logging.info(f"  Valid content: {stats['verification']['valid_content']}")
    logging.info(f"  Invalid content: {stats['verification']['invalid_content']}")
    logging.info(f"  Unverified: {stats['verification']['unverified']}")
    
    logging.info(f"\nElapsed time: {elapsed_str}")
    logging.info("="*50)
    logging.info(f"Failed downloads are logged in: {FAILED_DOWNLOADS_LOG}")
    logging.info(f"Sci-Hub attempts are logged in: {SCIHUB_ATTEMPTS_LOG}")
    logging.info(f"Content verification details are logged in: {CONTENT_VERIFICATION_LOG}")
    logging.info(f"Download statistics saved to: {STATS_FILE}")
    logging.info("="*50)

def main():
    global BASE_DIR, STATE_FILE, LOGS_DIR, FAILED_DOWNLOADS_LOG, SCIHUB_ATTEMPTS_LOG, STATS_FILE, CONTENT_VERIFICATION_LOG, FILE_TYPE_DIRS, SCIHUB_LOGS_DIR
    
    parser = argparse.ArgumentParser(description='Download files from a list of URLs with rate limiting, content verification, and resumable downloads. Falls back to Sci-Hub for non-PDF URLs or failed downloads.')
    parser.add_argument('url_list_file', help='Path to the file containing the list of URLs.')
    parser.add_argument('--max-concurrent', type=int, default=DEFAULT_RATE_LIMIT,
                        help=f'Maximum number of concurrent downloads. Default: {DEFAULT_RATE_LIMIT}')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                        help=f'Delay between downloads in seconds. Default: {DEFAULT_DELAY}')
    parser.add_argument('--scihub-delay', type=float, default=DEFAULT_SCIHUB_RATE_LIMIT_DELAY,
                        help=f'Delay between Sci-Hub requests in seconds. Default: {DEFAULT_SCIHUB_RATE_LIMIT_DELAY}')
    parser.add_argument('--base-dir', type=str, default=BASE_DIR,
                        help=f'Base directory to save downloaded files. Default: {BASE_DIR}')
    parser.add_argument('--state-file', type=str, default=STATE_FILE,
                        help=f'File to store download state. Default: {STATE_FILE}')
    parser.add_argument('--logs-dir', type=str, default=LOGS_DIR,
                        help=f'Directory to store log files. Default: {LOGS_DIR}')
    parser.add_argument('--verify-content', action='store_true', default=True,
                        help='Verify that downloaded content is valid and useful.')
    parser.add_argument('--disable-scihub', action='store_true',
                        help='Disable Sci-Hub fallback for non-PDF URLs or failed downloads.')
    parser.add_argument('--only-scihub', action='store_true',
                        help='Only use Sci-Hub for downloading (requires DOIs in URL list).')
    
    args = parser.parse_args()
    
    # Update global variables with command line arguments
    BASE_DIR = args.base_dir
    STATE_FILE = args.state_file
    LOGS_DIR = args.logs_dir
    FAILED_DOWNLOADS_LOG = os.path.join(LOGS_DIR, 'failed_downloads.log')
    SCIHUB_ATTEMPTS_LOG = os.path.join(LOGS_DIR, 'scihub_attempts.log')
    STATS_FILE = os.path.join(LOGS_DIR, 'download_stats.json')
    CONTENT_VERIFICATION_LOG = os.path.join(LOGS_DIR, 'content_verification.log')
    
    # Update file type directories
    FILE_TYPE_DIRS['pdf'] = os.path.join(BASE_DIR, 'pdf')
    FILE_TYPE_DIRS['sci_pdf'] = os.path.join(BASE_DIR, 'sci_pdf')
    
    # Create a logs directory within sci_pdf for Sci-Hub specific logs
    SCIHUB_LOGS_DIR = os.path.join(FILE_TYPE_DIRS['sci_pdf'], 'logs')
    
    # Set up logging
    failed_logger, scihub_logger, verification_logger = setup_logging()
    
    # Initialize stats
    stats['start_time'] = datetime.now().isoformat()
    load_stats()  # Load previous stats if available
    
    # Load previously downloaded URLs
    load_state()
    
    if not os.path.exists(args.url_list_file):
        logging.error(f"Error: URL list file not found at {args.url_list_file}")
        return
    
    # Read URLs from file
    with open(args.url_list_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    stats['total_urls'] = len(urls)
    logging.info(f"Found {len(urls)} URLs in {args.url_list_file}.")
    
    # Filter out already downloaded URLs for initial count
    urls_to_download = [url for url in urls if url not in downloaded_urls]
    stats['skipped_downloads'] = len(urls) - len(urls_to_download)
    logging.info(f"Skipping {stats['skipped_downloads']} URLs that were previously downloaded.")
    logging.info(f"Attempting to download {len(urls_to_download)} new URLs.")
    
    stats['attempted_downloads'] = len(urls_to_download)
    
    # Create directories
    for dir_path in FILE_TYPE_DIRS.values():
        os.makedirs(dir_path, exist_ok=True)
    os.makedirs(SCIHUB_LOGS_DIR, exist_ok=True)
    
    # Download the identified URLs with rate limiting
    if urls_to_download:
        logging.info(f"Starting downloads with max {args.max_concurrent} concurrent downloads, {args.delay}s delay between downloads, and {args.scihub_delay}s delay between Sci-Hub requests...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
            future_to_url = {
                executor.submit(
                    download_file, 
                    url, 
                    args.delay, 
                    failed_logger, 
                    scihub_logger, 
                    verification_logger,
                    args.scihub_delay
                ): url 
                for url in urls_to_download
            }
            
            # Use tqdm to show overall progress
            with tqdm(total=len(urls_to_download), desc="Overall Progress") as pbar:
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        future.result()  # We don't need the result, just wait for completion
                    except Exception as exc:
                        logging.error(f'{url} generated an exception: {exc}')
                    finally:
                        pbar.update(1)
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    main()