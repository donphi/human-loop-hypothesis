import os
import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def download_from_scihub_selenium(doi, output_path, rate_limit_delay=5):
    """Download a paper from Sci-Hub using Selenium browser automation."""
    if not doi:
        print(f"No DOI found, cannot use Sci-Hub")
        return False
    
    print(f"Attempting to download DOI {doi} from Sci-Hub using Selenium")
    
    # Apply rate limiting
    time.sleep(rate_limit_delay)
    
    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Set download directory
    download_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(download_dir, exist_ok=True)
    
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    })
    
    driver = None
    try:
        # Initialize the browser
        driver = webdriver.Chrome(options=chrome_options)
        
        # Go to Sci-Hub
        scihub_url = "https://www.sci-hub.ee"
        print(f"Navigating to {scihub_url}")
        driver.get(scihub_url)
        
        # Wait for the page to load
        time.sleep(3)
        
        # Save screenshot for debugging
        driver.save_screenshot(f"{download_dir}/scihub_homepage.png")
        print(f"Saved screenshot to {download_dir}/scihub_homepage.png")
        
        # Find the input field and enter the DOI
        try:
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "request"))
            )
            input_field.clear()
            input_field.send_keys(doi)
            print(f"Entered DOI {doi} into the input field")
            
            # Find and click the open button
            open_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "open"))
            )
            open_button.click()
            print("Clicked the open button")
            
            # Wait for the result page to load
            time.sleep(5)
            
            # Save screenshot of the result page
            driver.save_screenshot(f"{download_dir}/scihub_result.png")
            print(f"Saved screenshot to {download_dir}/scihub_result.png")
            
            # Try to find the PDF iframe
            iframe = None
            try:
                iframe = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
                print("Found iframe with PDF")
            except:
                print("No iframe found")
            
            if iframe and 'src' in iframe.get_attribute("outerHTML"):
                pdf_url = iframe.get_attribute("src")
                print(f"Found PDF URL in iframe: {pdf_url}")
                
                # If the PDF URL is relative, make it absolute
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    pdf_url = scihub_url + ('/' if not pdf_url.startswith('/') else '') + pdf_url
                
                # Download the PDF using requests
                print(f"Downloading PDF from {pdf_url}")
                pdf_response = requests.get(pdf_url, stream=True)
                pdf_response.raise_for_status()
                
                with open(output_path, 'wb') as f:
                    for chunk in pdf_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"Successfully downloaded PDF to {output_path}")
                return True
            else:
                # Try to find a download button
                download_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
                if download_links:
                    pdf_url = download_links[0].get_attribute("href")
                    print(f"Found PDF download link: {pdf_url}")
                    
                    # Download the PDF using requests
                    pdf_response = requests.get(pdf_url, stream=True)
                    pdf_response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        for chunk in pdf_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    print(f"Successfully downloaded PDF to {output_path}")
                    return True
                else:
                    print("Could not find PDF download link")
                    return False
            
        except Exception as e:
            print(f"Error interacting with Sci-Hub page: {e}")
            return False
        
    except Exception as e:
        print(f"Error in Selenium browser automation: {e}")
        return False
    
    finally:
        if driver:
            driver.quit()
            print("Closed browser")

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
            
            success = download_from_scihub_selenium(doi, output_path, rate_limit_delay=3)
            
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