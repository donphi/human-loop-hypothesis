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
STATS_FILE = os.path.join(LOGS_DIR, 'download_stats.json')
CONTENT_VERIFICATION_LOG = os.path.join(LOGS_DIR, 'content_verification.log')
DEFAULT_RATE_LIMIT = 5  # Default max concurrent downloads
DEFAULT_DELAY = 1.0  # Default delay between downloads in seconds
MIN_PDF_SIZE = 10 * 1024  # Minimum size for a valid PDF (10KB)
MIN_TEXT_CONTENT = 1000  # Minimum number of characters for valid text content

# File type directories
FILE_TYPE_DIRS = {
    'pdf': os.path.join(BASE_DIR, 'pdf'),
    'html': os.path.join(BASE_DIR, 'html'),
    'xml': os.path.join(BASE_DIR, 'xml'),
    'doc': os.path.join(BASE_DIR, 'doc'),
    'txt': os.path.join(BASE_DIR, 'txt'),
    'unknown': os.path.join(BASE_DIR, 'unknown')
}

# Global variables
downloaded_urls = set()
failed_urls = set()
verification_results = {}
start_time = None
stats = {
    'total_urls': 0,
    'attempted_downloads': 0,
    'successful_downloads': 0,
    'failed_downloads': 0,
    'skipped_downloads': 0,
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

# Set up logging
def setup_logging():
    """Set up logging configuration."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    
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
    
    # Create a separate logger for content verification
    verification_logger = logging.getLogger('content_verification')
    verification_logger.setLevel(logging.INFO)
    verification_handler = logging.FileHandler(CONTENT_VERIFICATION_LOG)
    verification_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    verification_logger.addHandler(verification_handler)
    
    return failed_logger, verification_logger

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
    # First check the Content-Type header
    content_type = response.headers.get('Content-Type', '').lower()
    
    if 'application/pdf' in content_type:
        return 'pdf'
    elif 'text/html' in content_type:
        return 'html'
    elif 'text/xml' in content_type or 'application/xml' in content_type:
        return 'xml'
    elif 'application/msword' in content_type or 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in content_type:
        return 'doc'
    elif 'text/plain' in content_type:
        return 'txt'
    
    # If header is not conclusive, try to guess from the first few bytes
    try:
        content_start = response.content[:1024]
        if content_start.startswith(b'%PDF'):
            return 'pdf'
        elif b'<!DOCTYPE HTML' in content_start or b'<html' in content_start:
            return 'html'
        elif b'<?xml' in content_start:
            return 'xml'
        elif b'PK\x03\x04' in content_start:  # DOCX files are ZIP archives
            return 'doc'
    except:
        pass
    
    # Default to unknown
    return 'unknown'

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

def verify_html_content(filepath, verification_logger):
    """Verify that an HTML file contains actual content and is not just a redirect or error page."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Check for minimum content length
        if len(content) < MIN_TEXT_CONTENT:
            verification_logger.info(f"HTML content too short ({len(content)} chars): {filepath}")
            return False, f"Content too short: {len(content)} characters"
        
        # Parse HTML
        soup = BeautifulSoup(content, 'html.parser')
        
        # Check for redirect meta tags
        meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
        if meta_refresh:
            verification_logger.info(f"HTML contains redirect meta tag: {filepath}")
            return False, "Contains redirect meta tag"
        
        # Check for redirect in URL parameters
        if 'Redirect=' in content or 'articleSelectPrefsTemp' in content:
            verification_logger.info(f"HTML appears to be a redirect page: {filepath}")
            return False, "Appears to be a redirect page"
        
        # Check for common error page indicators
        title = soup.title.text.lower() if soup.title else ""
        if any(err in title for err in ['error', '404', 'not found', 'redirect']):
            verification_logger.info(f"HTML appears to be an error page: {filepath}")
            return False, f"Appears to be an error page: {title}"
        
        # Check for actual content
        body_text = soup.body.get_text(strip=True) if soup.body else ""
        if len(body_text) < MIN_TEXT_CONTENT:
            verification_logger.info(f"HTML body has insufficient text ({len(body_text)} chars): {filepath}")
            return False, f"Insufficient body text: {len(body_text)} characters"
        
        verification_logger.info(f"Valid HTML content: {filepath}")
        return True, "Valid HTML content"
        
    except Exception as e:
        verification_logger.info(f"Error verifying HTML {filepath}: {e}")
        return False, f"Error verifying: {e}"

def verify_content(filepath, file_type, verification_logger):
    """Verify that the downloaded file contains valid, useful content."""
    if file_type == 'pdf':
        return verify_pdf_content(filepath, verification_logger)
    elif file_type == 'html':
        return verify_html_content(filepath, verification_logger)
    elif file_type in ['xml', 'txt']:
        # Basic check for text files
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if len(content) < MIN_TEXT_CONTENT:
                verification_logger.info(f"{file_type.upper()} content too short ({len(content)} chars): {filepath}")
                return False, f"Content too short: {len(content)} characters"
            verification_logger.info(f"Valid {file_type.upper()} content: {filepath}")
            return True, f"Valid {file_type.upper()} content"
        except Exception as e:
            verification_logger.info(f"Error verifying {file_type.upper()} {filepath}: {e}")
            return False, f"Error verifying: {e}"
    else:
        # For other file types, just check if the file exists and is not empty
        try:
            file_size = os.path.getsize(filepath)
            if file_size < 100:  # Arbitrary minimum size
                verification_logger.info(f"File too small ({file_size} bytes): {filepath}")
                return False, f"File too small: {file_size} bytes"
            verification_logger.info(f"File exists with size {file_size} bytes: {filepath}")
            return True, f"File exists with size {file_size} bytes"
        except Exception as e:
            verification_logger.info(f"Error checking file {filepath}: {e}")
            return False, f"Error checking file: {e}"

def download_file(url, delay=0, failed_logger=None, verification_logger=None):
    """Downloads a file from the given URL with content verification."""
    global stats, verification_results
    
    if url in downloaded_urls:
        logging.info(f"Skipping {url}: already downloaded.")
        stats['skipped_downloads'] += 1
        return False  # Indicate skipped
    
    # Apply rate limiting delay if specified
    if delay > 0:
        time.sleep(delay)
    
    try:
        # Check if the URL has associated metadata (from the new format of extracted_urls.txt)
        metadata_parts = None
        original_url = url
        if '|http' in url:
            parts = url.split('|')
            metadata_parts = parts[:-1]  # All parts except the last one (which is the URL)
            url = parts[-1]  # The actual URL is the last part
        
        # Generate filename and determine file type
        if metadata_parts and len(metadata_parts) >= 5:
            pub_id, doi, author, title, expected_file_type = metadata_parts
            # Create a filename with the format: DOI_Author_Title.ext
            # If DOI is empty or too short, use pub_id instead
            if not doi or len(doi) < 3:
                doi = pub_id
            
            # Ensure the filename has a reasonable length
            max_title_length = 40
            if len(title) > max_title_length:
                title = title[:max_title_length]
            
            filename_base = f"{doi}_{author}_{title}"
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
                expected_file_type = 'unknown'
                if url.lower().endswith('.pdf'):
                    expected_file_type = 'pdf'
                elif url.lower().endswith(('.html', '.htm')):
                    expected_file_type = 'html'
                elif url.lower().endswith('.xml'):
                    expected_file_type = 'xml'
            # Clean up filename
            if not filename_base or len(filename_base) < 5:
                # Generate a filename if not available or invalid
                filename_base = f"downloaded_file_{len(downloaded_urls) + 1}"
            
            # Try to guess file type from URL
            expected_file_type = 'unknown'
            if url.lower().endswith('.pdf'):
                expected_file_type = 'pdf'
            elif url.lower().endswith(('.html', '.htm')):
                expected_file_type = 'html'
            elif url.lower().endswith('.xml'):
                expected_file_type = 'xml'
        
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
        
        # Create directories for each file type if they don't exist
        for dir_path in FILE_TYPE_DIRS.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # Temporary filepath for initial download
        # Use a hash of the URL to create a unique but short identifier to avoid path length issues
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        temp_filepath = os.path.join(BASE_DIR, f"temp_{url_hash}")
        
        logging.info(f"Downloading {url} to temporary file...")
        # Allow redirects and set a reasonable timeout
        response = requests.get(url, stream=True, timeout=30, allow_redirects=True)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        
        # For HTML content, check if it's a redirect page and follow the redirect if needed
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type or 'application/xhtml+xml' in content_type:
            # Get the first chunk to check for redirects
            content_preview = next(response.iter_content(chunk_size=8192), b'')
            response_text = content_preview.decode('utf-8', errors='ignore')
            
            # Check if this is a redirect page
            redirect_url = extract_redirect_url(response_text, url)
            if redirect_url:
                logging.info(f"Found redirect URL in HTML content: {redirect_url}")
                
                # Close the current response
                response.close()
                
                # Follow the redirect URL
                logging.info(f"Following redirect to: {redirect_url}")
                response = requests.get(redirect_url, stream=True, timeout=30, allow_redirects=True)
                response.raise_for_status()
        
        # Detect actual content type from response
        actual_file_type = detect_content_type(response)
        
        # Update file type statistics
        stats['file_types'][actual_file_type] = stats['file_types'].get(actual_file_type, 0) + 1
        
        # Determine final file extension and path
        if actual_file_type == 'pdf':
            ext = '.pdf'
        elif actual_file_type == 'html':
            ext = '.html'
        elif actual_file_type == 'xml':
            ext = '.xml'
        elif actual_file_type == 'doc':
            ext = '.docx' if 'openxmlformats' in response.headers.get('Content-Type', '') else '.doc'
        elif actual_file_type == 'txt':
            ext = '.txt'
        else:
            # Try to get extension from URL or use .bin
            url_ext = os.path.splitext(urlparse(url).path)[1]
            ext = url_ext if url_ext else '.bin'
        
        # Ensure filename has the correct extension and is not too long
        # Limit the base filename length to avoid path length issues
        max_base_length = 40
        if len(filename_base) > max_base_length:
            filename_base = filename_base[:max_base_length]
            # Remove trailing underscores or punctuation
            filename_base = re.sub(r'[_\-.,;:]+$', '', filename_base)
            
        if not filename_base.lower().endswith(ext.lower()):
            filename = filename_base + ext
        else:
            filename = filename_base
        
        # Determine final filepath based on detected file type
        filepath = os.path.join(FILE_TYPE_DIRS.get(actual_file_type, FILE_TYPE_DIRS['unknown']), filename)
        
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
        else:
            stats['verification']['invalid_content'] += 1
        
        downloaded_urls.add(original_url)
        stats['successful_downloads'] += 1
        logging.info(f"Successfully downloaded {url} to {filepath}")
        logging.info(f"Content verification: {'VALID' if is_valid else 'INVALID'} - {reason}")
        return True  # Indicate success
    
    except requests.exceptions.RequestException as e:
        stats['failed_downloads'] += 1
        error_msg = f"Error downloading {url}: {e}"
        logging.error(error_msg)
        if failed_logger:
            failed_logger.error(f"{original_url if 'original_url' in locals() else url} - {e}")
        failed_urls.add(original_url if 'original_url' in locals() else url)
        return False  # Indicate failure
    
    except IOError as e:
        stats['failed_downloads'] += 1
        error_msg = f"Error writing file for {url}: {e}"
        logging.error(error_msg)
        if failed_logger:
            failed_logger.error(f"{original_url if 'original_url' in locals() else url} - {e}")
        failed_urls.add(original_url if 'original_url' in locals() else url)
        return False  # Indicate failure
    
    except Exception as e:
        stats['failed_downloads'] += 1
        error_msg = f"Unexpected error processing {url}: {e}"
        logging.error(error_msg)
        if failed_logger:
            failed_logger.error(f"{original_url if 'original_url' in locals() else url} - {e}")
        failed_urls.add(original_url if 'original_url' in locals() else url)
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
    logging.info(f"Content verification details are logged in: {CONTENT_VERIFICATION_LOG}")
    logging.info(f"Download statistics saved to: {STATS_FILE}")
    logging.info("="*50)

def process_existing_html_redirects(verification_logger=None):
    """
    Process existing HTML files that contain redirects and replace them with the actual content.
    This is useful for fixing previously downloaded HTML files that are just redirect pages.
    """
    html_dir = FILE_TYPE_DIRS.get('html')
    if not os.path.exists(html_dir):
        logging.info(f"HTML directory {html_dir} does not exist, skipping redirect processing.")
        return
    
    logging.info(f"Checking for redirect HTML files in {html_dir}...")
    redirect_files = []
    
    # Find HTML files that might be redirects
    for filename in os.listdir(html_dir):
        if not filename.endswith('.html'):
            continue
        
        filepath = os.path.join(html_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check if this is a redirect file
            if 'Redirect=' in content or 'articleSelectPrefsTemp' in content:
                # Use the original URL from the index if available, otherwise use a default base
                base_url = None
                for pub_id, pub_data in getattr(download_file, 'publication_index', {}).items():
                    if filename in pub_data.get('filepath', ''):
                        base_url = pub_data.get('url')
                        break
                
                redirect_url = extract_redirect_url(content, base_url)
                if redirect_url:
                    redirect_files.append((filepath, filename, redirect_url))
        except Exception as e:
            logging.error(f"Error checking HTML file {filepath}: {e}")
    
    if not redirect_files:
        logging.info("No redirect HTML files found.")
        return
    
    logging.info(f"Found {len(redirect_files)} HTML files with redirects. Processing...")
    
    # Process each redirect file
    for filepath, filename, redirect_url in redirect_files:
        logging.info(f"Processing redirect in {filename} to {redirect_url}")
        
        try:
            # Download the actual content
            response = requests.get(redirect_url, stream=True, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Create a temporary file
            temp_filepath = filepath + ".tmp"
            
            # Save the content to the temporary file
            with open(temp_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify the content
            is_valid, reason = verify_content(temp_filepath, 'html', verification_logger)
            
            if is_valid:
                # Replace the original file with the new content
                os.replace(temp_filepath, filepath)
                logging.info(f"Successfully replaced redirect file {filename} with actual content.")
            else:
                # If not valid, keep the original file but log the issue
                os.remove(temp_filepath)
                logging.warning(f"Downloaded content for {filename} was not valid: {reason}")
        
        except Exception as e:
            logging.error(f"Error processing redirect in {filename}: {e}")

def main():
    # Declare globals at the beginning of the function
    global DOWNLOAD_DIR, STATE_FILE, LOGS_DIR, FAILED_DOWNLOADS_LOG, STATS_FILE, BASE_DIR, FILE_TYPE_DIRS, stats
    
    parser = argparse.ArgumentParser(description='Download files from a list of URLs with rate limiting, content verification, and resumable downloads.')
    parser.add_argument('url_list_file', help='Path to the file containing the list of URLs.')
    parser.add_argument('--max-concurrent', type=int, default=DEFAULT_RATE_LIMIT,
                        help=f'Maximum number of concurrent downloads. Default: {DEFAULT_RATE_LIMIT}')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY,
                        help=f'Delay between downloads in seconds. Default: {DEFAULT_DELAY}')
    parser.add_argument('--base-dir', type=str, default=BASE_DIR,
                        help=f'Base directory to save downloaded files. Default: {BASE_DIR}')
    parser.add_argument('--state-file', type=str, default=STATE_FILE,
                        help=f'File to store download state. Default: {STATE_FILE}')
    parser.add_argument('--logs-dir', type=str, default=LOGS_DIR,
                        help=f'Directory to store log files. Default: {LOGS_DIR}')
    parser.add_argument('--check-content-type', action='store_true',
                        help='Check if URL points to a PDF before downloading.')
    parser.add_argument('--verify-content', action='store_true', default=True,
                        help='Verify that downloaded content is valid and useful.')
    parser.add_argument('--process-redirects', action='store_true',
                        help='Process existing HTML files that contain redirects and replace them with actual content.')
    
    args = parser.parse_args()
    
    # Update global variables with command line arguments
    BASE_DIR = args.base_dir
    STATE_FILE = args.state_file
    LOGS_DIR = args.logs_dir
    FAILED_DOWNLOADS_LOG = os.path.join(LOGS_DIR, 'failed_downloads.log')
    STATS_FILE = os.path.join(LOGS_DIR, 'download_stats.json')
    
    # Update file type directories
    for file_type in FILE_TYPE_DIRS:
        FILE_TYPE_DIRS[file_type] = os.path.join(BASE_DIR, file_type)
    
    # Set up logging
    failed_logger, verification_logger = setup_logging()
    
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
    
    # Check if URLs are PDFs if requested
    if args.check_content_type:
        logging.info("Checking content types...")
        pdf_urls = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
            future_to_url = {executor.submit(is_pdf, url): url for url in urls_to_download}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
                url = future_to_url[future]
                try:
                    is_pdf_result = future.result()
                    if is_pdf_result:
                        pdf_urls.append(url)
                    if (i+1) % 10 == 0:  # Log progress every 10 URLs
                        logging.info(f"Checked {i+1}/{len(urls_to_download)} URLs.")
                except Exception as exc:
                    logging.error(f'{url} generated an exception during check: {exc}')
        
        logging.info(f"Found {len(pdf_urls)} PDF URLs to download.")
        urls_to_download = pdf_urls
    
    stats['attempted_downloads'] = len(urls_to_download)
    
    # Create base directory and file type subdirectories
    os.makedirs(BASE_DIR, exist_ok=True)
    for dir_path in FILE_TYPE_DIRS.values():
        os.makedirs(dir_path, exist_ok=True)
    
    # Download the identified URLs with rate limiting
    if urls_to_download:
        logging.info(f"Starting downloads with max {args.max_concurrent} concurrent downloads and {args.delay}s delay between downloads...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
            future_to_url = {
                executor.submit(download_file, url, args.delay, failed_logger, verification_logger): url 
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
    
    # Process existing HTML files with redirects if requested
    if args.process_redirects:
        logging.info("Processing existing HTML files with redirects...")
        process_existing_html_redirects(verification_logger)
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    main()