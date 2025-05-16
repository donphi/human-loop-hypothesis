import os
import time
import json
import re
import requests
from bs4 import BeautifulSoup

def download_from_scihub(doi, output_path, rate_limit_delay=5):
    """Download a paper from Sci-Hub using direct form submission."""
    if not doi:
        print(f"No DOI found, cannot use Sci-Hub")
        return False
    
    print(f"Attempting to download DOI {doi} from Sci-Hub")
    
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
    
    # List of Sci-Hub domains to try
    scihub_domains = [
    ]
    
    for scihub_url in scihub_domains:
        try:
            print(f"Trying Sci-Hub domain: {scihub_url}")
            
            # First get the main page to get any cookies
            main_response = session.get(scihub_url, headers=headers, timeout=10)
            
            if main_response.status_code != 200:
                print("Waiting 5 seconds after initiating page...")
                time.sleep(5)
                print(f"Failed to access {scihub_url}: {main_response.status_code}")
                continue
            
            print(f"Successfully accessed {scihub_url}")
            
            # Submit the DOI
            data = {
                'request': doi,
                'sci-hub-plugin-check': ''
            }
            
            response = session.post(scihub_url, data=data, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print("Waiting 15 seconds after submitting DOI...")
                time.sleep(15)
                print(f"Failed to submit DOI to {scihub_url}: {response.status_code}")
                continue
            
            print(f"Successfully submitted DOI to {scihub_url}")
            
            # Save the response HTML for debugging
            debug_path = f"scihub_test/debug_response_{doi.replace('/', '_')}.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"Saved response HTML to {debug_path}")
            
            # Parse the response to find the PDF
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the PDF iframe
            iframe = soup.find('iframe')
            if iframe and iframe.get('src'):
                pdf_url = iframe.get('src')
                print(f"Found PDF URL in iframe: {pdf_url}")
                
                # If the PDF URL is relative, make it absolute
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
                
                # Download the PDF
                print(f"Downloading PDF from {pdf_url}")
                pdf_response = session.get(pdf_url, headers=headers, stream=True)
                
                if pdf_response.status_code != 200:
                    print(f"Failed to download PDF: {pdf_response.status_code}")
                    continue
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                
                # Save the PDF
                with open(output_path, 'wb') as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"Successfully downloaded PDF to {output_path}")
                return True
            
            # If no iframe, look for download links
            download_links = []
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if href.endswith('.pdf') or 'pdf' in href.lower():
                    download_links.append(href)
            
            if download_links:
                pdf_url = download_links[0]
                print(f"Found PDF download link: {pdf_url}")
                
                # If the PDF URL is relative, make it absolute
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
                
                # Download the PDF
                pdf_response = session.get(pdf_url, headers=headers, stream=True)
                
                if pdf_response.status_code != 200:
                    print(f"Failed to download PDF: {pdf_response.status_code}")
                    continue
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                
                # Save the PDF
                with open(output_path, 'wb') as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"Successfully downloaded PDF to {output_path}")
                return True
            
            # If no iframe or download link, look for embed tag within article div
            article_div = soup.find('div', id='article')
            if article_div:
                embed_tag = article_div.find('embed')
                if embed_tag and embed_tag.get('src'):
                    pdf_url = embed_tag.get('src')
                    print(f"Found PDF URL in embed tag: {pdf_url}")

                    # If the PDF URL is relative, make it absolute
                    if pdf_url.startswith('//'):
                        pdf_url = 'https:' + pdf_url
                    elif not pdf_url.startswith(('http://', 'https://')):
                        pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url

                    # Download the PDF
                    print(f"Downloading PDF from {pdf_url}")
                    pdf_response = session.get(pdf_url, headers=headers, stream=True)

                    if pdf_response.status_code != 200:
                        print(f"Failed to download PDF: {pdf_response.status_code}")
                        continue

                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

                    # Save the PDF
                    with open(output_path, 'wb') as f:
                        for chunk in pdf_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                    print(f"Successfully downloaded PDF to {output_path}")
                    return True

            # If still no PDF found, try to extract from JavaScript
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    pdf_matches = re.findall(r'https?://[^\s\'"]+\.pdf', script.string)
                    if pdf_matches:
                        pdf_url = pdf_matches[0]
                        print(f"Found PDF URL in script: {pdf_url}")
                        
                        # Download the PDF
                        pdf_response = session.get(pdf_url, headers=headers, stream=True)
                        
                        if pdf_response.status_code != 200:
                            print(f"Failed to download PDF: {pdf_response.status_code}")
                            continue
                        
                        # Ensure the directory exists
                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        
                        # Save the PDF
                        with open(output_path, 'wb') as f:
                            for chunk in pdf_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        print(f"Successfully downloaded PDF to {output_path}")
                        return True
            
            print(f"Could not find PDF on {scihub_url}")
            
        except Exception as e:
            print(f"Error with {scihub_url}: {e}")
    
    print("All Sci-Hub domains failed")
    return False

def main():
    # Create output directory
    os.makedirs("scihub_test", exist_ok=True)
    
    # Load a few DOIs from the publication index
    try:
        with open("index/publications_index.json", "r") as f:
            publications = json.load(f)
        
        # Get a few DOIs to test
        test_dois = []
        for pub_id, pub_data in publications.items():
            if "doi" in pub_data and pub_data["doi"]:
                test_dois.append(pub_data["doi"])
                if len(test_dois) >= 3:
                    break
        
        if not test_dois:
            print("No DOIs found in the publication index")
            return
        
        print(f"Found {len(test_dois)} DOIs to test")
        
        # Test each DOI
        for i, doi in enumerate(test_dois):
            print("\n" + "="*50)
            print(f"Testing DOI: {doi}")
            print("="*50)
            
            output_path = f"scihub_test/test_{i+1}_{doi.replace('/', '_')}.pdf"
            
            success = download_from_scihub(doi, output_path, rate_limit_delay=3)
            
            if success:
                file_size = os.path.getsize(output_path)
                print(f"Download successful: {file_size} bytes")
                
                # Check if it's a PDF
                with open(output_path, 'rb') as f:
                    content_start = f.read(1024)
                    if content_start.startswith(b'%PDF'):
                        print("File is a valid PDF")
                    else:
                        print("File does not appear to be a valid PDF")
            else:
                print("Download failed")
        
    except Exception as e:
        print(f"Error loading publication index: {e}")

if __name__ == "__main__":
    main()