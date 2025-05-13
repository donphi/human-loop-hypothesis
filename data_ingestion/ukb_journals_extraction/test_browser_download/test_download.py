import requests
import os
import sys
import time
from urllib.parse import urlparse, parse_qs

def download_with_requests(url, output_path):
    """Standard download using requests library"""
    print(f"Downloading {url} with requests...")
    
    # Use a browser-like user agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Download with stream=True to handle large files
    response = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
    response.raise_for_status()
    
    # Save the content
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    print(f"Downloaded to {output_path}")
    return os.path.getsize(output_path)

def download_with_curl(url, output_path):
    """Download using curl command which can handle some browser-specific URLs better"""
    print(f"Downloading {url} with curl...")
    
    # Use curl with browser-like user agent and follow redirects
    os.system(f'curl -L -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" "{url}" -o "{output_path}"')
    
    print(f"Downloaded to {output_path}")
    return os.path.getsize(output_path)

def check_file_type(file_path):
    """Check if the file is a PDF or HTML"""
    with open(file_path, 'rb') as f:
        content = f.read(1024)  # Read first 1KB
        
    if content.startswith(b'%PDF'):
        return "PDF"
    elif b'<!DOCTYPE HTML' in content or b'<html' in content:
        return "HTML"
    else:
        return "Unknown"

def main():
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Test URLs
    test_urls = [
        # PLOS One printable URL
        "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0154222&type=printable",
        # EuropePMC render URL
        "https://europepmc.org/articles/pmc5079686?pdf=render"
    ]
    
    results = []
    
    for url in test_urls:
        print("\n" + "="*50)
        print(f"Testing URL: {url}")
        print("="*50)
        
        # Parse URL to get a filename
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        if 'id' in query_params:
            filename = query_params['id'][0].replace('/', '_')
        else:
            # Use the last part of the path
            path_parts = parsed_url.path.split('/')
            filename = path_parts[-1] if path_parts[-1] else path_parts[-2]
        
        # Test with requests
        requests_output = f"output/requests_{filename}.bin"
        try:
            requests_size = download_with_requests(url, requests_output)
            requests_type = check_file_type(requests_output)
            print(f"Requests download: {requests_size} bytes, type: {requests_type}")
        except Exception as e:
            print(f"Requests download failed: {e}")
            requests_size = 0
            requests_type = "Failed"
        
        # Test with curl
        curl_output = f"output/curl_{filename}.bin"
        try:
            curl_size = download_with_curl(url, curl_output)
            curl_type = check_file_type(curl_output)
            print(f"Curl download: {curl_size} bytes, type: {curl_type}")
        except Exception as e:
            print(f"Curl download failed: {e}")
            curl_size = 0
            curl_type = "Failed"
        
        # Compare results
        results.append({
            'url': url,
            'requests': {'size': requests_size, 'type': requests_type},
            'curl': {'size': curl_size, 'type': curl_type}
        })
        
        # Small delay between downloads
        time.sleep(2)
    
    # Print summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    for result in results:
        print(f"\nURL: {result['url']}")
        print(f"Requests: {result['requests']['size']} bytes, type: {result['requests']['type']}")
        print(f"Curl: {result['curl']['size']} bytes, type: {result['curl']['type']}")
        
        if result['requests']['type'] == 'PDF' and result['curl']['type'] == 'PDF':
            print("Both methods successfully downloaded PDF")
        elif result['requests']['type'] == 'PDF':
            print("Only requests successfully downloaded PDF")
        elif result['curl']['type'] == 'PDF':
            print("Only curl successfully downloaded PDF")
        else:
            print("Neither method successfully downloaded PDF")

if __name__ == "__main__":
    main()