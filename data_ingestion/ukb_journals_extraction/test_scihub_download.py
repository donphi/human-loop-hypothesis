import requests
import re
import os
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

def extract_doi_from_url(url):
    """Extract DOI from a URL or return the URL if it's already a DOI."""
    # Check if it's a DOI URL (e.g., https://doi.org/10.1038/s41593-018-0206-1)
    if 'doi.org' in url:
        doi_match = re.search(r'10\.\d{4,}[\/\\].+?(?=[\/\\&?]|$)', url)
        if doi_match:
            return doi_match.group(0)
    
    # Check if it's already a DOI (e.g., 10.1038/s41593-018-0206-1)
    if url.startswith('10.'):
        return url
    
    # Try to extract DOI from other URL formats
    doi_match = re.search(r'10\.\d{4,}[\/\\].+?(?=[\/\\&?]|$)', url)
    if doi_match:
        return doi_match.group(0)
    
    return None

def download_from_scihub(doi, output_path, rate_limit_delay=5):
    """Download a paper from Sci-Hub using its DOI."""
    if not doi:
        print(f"No DOI found, cannot use Sci-Hub")
        return False
    
    print(f"Attempting to download DOI {doi} from Sci-Hub")
    
    # Apply rate limiting
    time.sleep(rate_limit_delay)
    
    # List of Sci-Hub domains to try
    scihub_domains = [
        "https://www.sci-hub.ee",
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru"
    ]
    
    session = requests.Session()
    
    # Set a browser-like User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    # Try each Sci-Hub domain
    for scihub_url in scihub_domains:
        print(f"Trying Sci-Hub domain: {scihub_url}")
        
        try:
            # First get the main page to get any cookies
            main_response = session.get(scihub_url, headers=headers, timeout=10)
            
            if main_response.status_code != 200:
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
                print(f"Failed to submit DOI to {scihub_url}: {response.status_code}")
                continue
            
            print(f"Successfully submitted DOI to {scihub_url}")
            
            # Check if the response contains a captcha
            if 'captcha' in response.text.lower():
                print(f"Captcha detected on {scihub_url}, trying next domain")
                continue
                
            # If we got here, we have a valid response to process
            break
            
        except Exception as e:
            print(f"Error accessing {scihub_url}: {e}")
            continue
    else:
        # This executes if the for loop completes without a break
        print("All Sci-Hub domains failed")
        return False
    
    # Step 2: Parse the response to find the PDF download link
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Debug: Save the HTML content to a file for inspection
    with open(f"scihub_test/debug_response_{doi.replace('/', '_')}.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    
    print(f"Saved HTML response to scihub_test/debug_response_{doi.replace('/', '_')}.html")
    
    # Look for the download button or iframe with PDF
    pdf_link = None
    
    # Debug: Print all buttons
    print("Searching for download buttons...")
    buttons = soup.select('#buttons a')
    print(f"Found {len(buttons)} buttons with #buttons a selector")
    for i, button in enumerate(buttons):
        print(f"Button {i+1}: {button}")
    
    # Check for the download button
    download_button = soup.select_one('#buttons a')
    if download_button and 'href' in download_button.attrs:
        pdf_link = download_button['href']
        print(f"Found download button with href: {pdf_link}")
    
    # If no download button, check for iframe
    if not pdf_link:
        print("Searching for iframe...")
        iframes = soup.select('iframe')
        print(f"Found {len(iframes)} iframes")
        for i, iframe in enumerate(iframes):
            print(f"Iframe {i+1}: {iframe}")
        
        iframe = soup.select_one('iframe#pdf')
        if iframe and 'src' in iframe.attrs:
            pdf_link = iframe['src']
            print(f"Found iframe with src: {pdf_link}")
    
    # If still no link, try other methods
    if not pdf_link:
        print("Trying alternative methods to find PDF link...")
        
        # Try to extract from JavaScript
        print("Looking for PDF link in JavaScript...")
        script_tags = soup.select('script')
        print(f"Found {len(script_tags)} script tags")
        
        for script in script_tags:
            if script.string:
                # Look for PDF URLs in JavaScript
                pdf_matches = re.findall(r'https?://[^\s\'"]+\.pdf', script.string)
                if pdf_matches:
                    print(f"Found PDF URL in script: {pdf_matches[0]}")
                    pdf_link = pdf_matches[0]
                    break
        
        # Try to find any element with 'save' or 'download' text
        if not pdf_link:
            save_elements = soup.find_all(text=re.compile(r'save|download|get|pdf', re.I))
            print(f"Found {len(save_elements)} elements with save/download/get/pdf text")
            for i, elem in enumerate(save_elements):
                parent = elem.parent
                if parent.name == 'a' and 'href' in parent.attrs:
                    print(f"Found potential download link: {parent['href']}")
                    pdf_link = parent['href']
                    break
        
        # Look for any link that might be a PDF
        if not pdf_link:
            pdf_links = []
            for link in soup.select('a'):
                if 'href' in link.attrs and (link['href'].endswith('.pdf') or 'pdf' in link['href']):
                    pdf_links.append(link['href'])
            
            print(f"Found {len(pdf_links)} links containing 'pdf'")
            for i, link in enumerate(pdf_links):
                print(f"PDF link {i+1}: {link}")
            
            if pdf_links:
                pdf_link = pdf_links[0]
                print(f"Using first PDF link: {pdf_link}")
        
        # Try to find embedded object or embed tags
        if not pdf_link:
            print("Looking for object or embed tags...")
            objects = soup.select('object')
            print(f"Found {len(objects)} object tags")
            for obj in objects:
                if 'data' in obj.attrs:
                    print(f"Found object with data: {obj['data']}")
                    if obj['data'].endswith('.pdf') or 'pdf' in obj['data'].lower():
                        pdf_link = obj['data']
                        break
            
            if not pdf_link:
                embeds = soup.select('embed')
                print(f"Found {len(embeds)} embed tags")
                for embed in embeds:
                    if 'src' in embed.attrs:
                        print(f"Found embed with src: {embed['src']}")
                        if embed['src'].endswith('.pdf') or 'pdf' in embed['src'].lower():
                            pdf_link = embed['src']
                            break
        
        # Last resort: try to find any URL that looks like a PDF in the entire HTML
        if not pdf_link:
            print("Searching entire HTML for PDF URLs...")
            pdf_urls = re.findall(r'https?://[^\s\'"]+\.pdf', response.text)
            if pdf_urls:
                print(f"Found {len(pdf_urls)} PDF URLs in HTML")
                for i, url in enumerate(pdf_urls):
                    print(f"PDF URL {i+1}: {url}")
                pdf_link = pdf_urls[0]
    
    if not pdf_link:
        print(f"Could not find PDF download link on Sci-Hub page")
        return False
    
    # Ensure the PDF link is absolute
    if pdf_link.startswith('//'):
        pdf_link = 'https:' + pdf_link
    elif not pdf_link.startswith(('http://', 'https://')):
        # Relative URL - join with base URL
        base_url = '{uri.scheme}://{uri.netloc}'.format(uri=urlparse(response.url))
        pdf_link = base_url + ('/' if not pdf_link.startswith('/') else '') + pdf_link
    
    print(f"Found PDF link: {pdf_link}")
    
    # Step 3: Download the PDF
    try:
        pdf_response = session.get(pdf_link, headers=headers, stream=True)
        pdf_response.raise_for_status()
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Save the PDF
        with open(output_path, 'wb') as f:
            for chunk in pdf_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"Successfully downloaded to {output_path}")
        return True
    
    except Exception as e:
        print(f"Error downloading PDF from Sci-Hub: {e}")
        return False

def main():
    # Create output directory
    os.makedirs("scihub_test", exist_ok=True)
    
    # Test DOIs
    test_urls = [
        "https://doi.org/10.1038/s41593-018-0206-1",
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6836675",
        "10.1038/s41467-019-12764-8"  # Direct DOI
    ]
    
    for i, url in enumerate(test_urls):
        print("\n" + "="*50)
        print(f"Testing URL: {url}")
        print("="*50)
        
        # Extract DOI
        doi = extract_doi_from_url(url)
        if doi:
            print(f"Extracted DOI: {doi}")
            
            # Create a filename based on DOI
            filename = doi.replace('/', '_').replace('\\', '_')
            output_path = f"scihub_test/test_{i+1}_{filename}.pdf"
            
            # Try to download from Sci-Hub
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
        else:
            print(f"Could not extract DOI from {url}")
    
    print("\nTest completed")

if __name__ == "__main__":
    main()