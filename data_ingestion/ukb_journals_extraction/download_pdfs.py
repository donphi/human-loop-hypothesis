import requests
import os
import json
import argparse
import concurrent.futures
import atexit
from urllib.parse import urlparse

STATE_FILE = '/app/download_state.json'
DOWNLOAD_DIR = '/app/downloaded_pdfs'

downloaded_urls = set()

def load_state():
    """Loads the set of downloaded URLs from the state file."""
    global downloaded_urls
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                downloaded_urls = set(json.load(f))
            print(f"Loaded {len(downloaded_urls)} previously downloaded URLs from state file.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading state file {STATE_FILE}: {e}")
            downloaded_urls = set() # Start fresh if state file is corrupt

def save_state():
    """Saves the set of downloaded URLs to the state file."""
    if downloaded_urls:
        try:
            # Ensure the directory for the state file exists
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump(list(downloaded_urls), f)
            print(f"Saved {len(downloaded_urls)} downloaded URLs to state file.")
        except IOError as e:
            print(f"Error saving state file {STATE_FILE}: {e}")

# Register save_state to be called on script exit
atexit.register(save_state)

def is_pdf(url):
    """Checks if the URL points to a PDF using a HEAD request."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        content_type = response.headers.get('Content-Type', '').lower()
        return 'application/pdf' in content_type
    except requests.exceptions.RequestException as e:
        print(f"Error checking URL {url}: {e}")
        return False

def download_pdf(url):
    """Downloads a PDF file from the given URL."""
    if url in downloaded_urls:
        print(f"Skipping {url}: already downloaded.")
        return False # Indicate skipped

    try:
        # Ensure download directory exists
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # Try to get filename from URL
        parsed_url = urlparse(url)
        path = parsed_url.path
        filename = os.path.basename(path)
        if not filename or '.' not in filename:
            # Generate a filename if not available or invalid
            filename = f"downloaded_pdf_{len(downloaded_urls) + 1}.pdf"

        filepath = os.path.join(DOWNLOAD_DIR, filename)

        print(f"Downloading {url} to {filepath}...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        downloaded_urls.add(url)
        print(f"Successfully downloaded {url}")
        return True # Indicate success

    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False # Indicate failure
    except IOError as e:
        print(f"Error writing file {filepath}: {e}")
        return False # Indicate failure

def main():
    parser = argparse.ArgumentParser(description='Download PDF files from a list of URLs.')
    parser.add_argument('url_list_file', help='Path to the file containing the list of URLs.')
    parser.add_argument('--max-concurrent', type=int, default=5,
                        help='Maximum number of concurrent downloads.')

    args = parser.parse_args()

    if not os.path.exists(args.url_list_file):
        print(f"Error: URL list file not found at {args.url_list_file}")
        return

    load_state()

    with open(args.url_list_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Found {len(urls)} URLs in {args.url_list_file}.")

    # Filter out already downloaded URLs for initial count
    urls_to_download = [url for url in urls if url not in downloaded_urls]
    skipped_count = len(urls) - len(urls_to_download)
    print(f"Skipping {skipped_count} URLs that were previously downloaded.")
    print(f"Attempting to download {len(urls_to_download)} new URLs.")


    # First, check if URLs are PDFs concurrently
    print("Checking content types...")
    pdf_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
        future_to_url = {executor.submit(is_pdf, url): url for url in urls_to_download}
        for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
            url = future_to_url[future]
            try:
                is_pdf_result = future.result()
                if is_pdf_result:
                    pdf_urls.append(url)
                # Optional: print progress for checking
                # print(f"Checked {i+1}/{len(urls_to_download)} URLs.")
            except Exception as exc:
                print(f'{url} generated an exception during check: {exc}')

    print(f"Found {len(pdf_urls)} PDF URLs to download.")

    # Then, download the identified PDF URLs concurrently
    downloaded_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
        future_to_url = {executor.submit(download_pdf, url): url for url in pdf_urls}
        for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
            url = future_to_url[future]
            try:
                download_success = future.result()
                if download_success:
                    downloaded_count += 1
                print(f"Processed {i+1}/{len(pdf_urls)} PDF URLs for download.")
            except Exception as exc:
                print(f'{url} generated an exception during download: {exc}')

    print(f"\nDownload complete.")
    print(f"Total URLs processed: {len(urls)}")
    print(f"Skipped (previously downloaded): {skipped_count}")
    print(f"Attempted PDF downloads: {len(pdf_urls)}")
    print(f"Successfully downloaded: {downloaded_count}")
    print(f"Failed downloads: {len(pdf_urls) - downloaded_count}")


if __name__ == "__main__":
    main()