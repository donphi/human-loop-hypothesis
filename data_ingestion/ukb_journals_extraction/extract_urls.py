import re
import os
import csv
import json
import argparse
from datetime import datetime

# Constants
INDEX_DIR = "index"
INDEX_FILE = os.path.join(INDEX_DIR, "publications_index.json")

def clean_text(text):
    """Clean text for use in filenames by removing invalid characters."""
    if not text:
        return ""
    
    # First decode HTML entities if present
    try:
        import html
        text = html.unescape(text)
    except (ImportError, AttributeError):
        # Fallback for basic HTML entities if html module is not available
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        # Handle numeric entities like &#233;
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    
    # Replace characters that are problematic in filenames
    cleaned = re.sub(r'[\\/*?:"<>|]', '', text)
    
    # Handle parentheses in DOIs - replace with square brackets which are safer
    cleaned = cleaned.replace('(', '[').replace(')', ']')
    
    # Replace spaces and other separators with underscores
    cleaned = re.sub(r'[\s,;]+', '_', cleaned)
    
    # Remove any duplicate underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # Remove trailing underscores or punctuation
    cleaned = re.sub(r'[_\-.,;:]+$', '', cleaned)
    
    return cleaned

def shorten_title(title, max_length=40):
    """Shorten the title to a reasonable length for a filename."""
    if not title:
        return ""
    if len(title) <= max_length:
        return title
    
    # Try to cut at a word boundary
    shortened = title[:max_length].rsplit(' ', 1)[0]
    
    # Remove trailing underscores or punctuation
    shortened = re.sub(r'[_\-.,;:]+$', '', shortened)
    
    return shortened

def extract_first_author(authors):
    """Extract the first author's last name from the authors field."""
    if not authors:
        return "Unknown"
    
    # Split by pipe or comma to get the first author
    first_author = re.split(r'[|,]', authors)[0].strip()
    
    # Extract the last name (assuming format is "First Last" or "Last, First")
    if '|' in authors:  # Format like "First Last|Another Name"
        last_name = first_author.split()[-1]
    else:  # Format might be "Last, First"
        last_name = first_author.split()[0]
    
    return last_name

def guess_file_type(url):
    """Guess the file type based on the URL."""
    url_lower = url.lower()
    
    # Check for explicit file extensions
    if url_lower.endswith('.pdf'):
        return 'pdf'
    elif url_lower.endswith(('.html', '.htm')):
        return 'html'
    elif url_lower.endswith('.xml'):
        return 'xml'
    elif url_lower.endswith(('.doc', '.docx')):
        return 'doc'
    elif url_lower.endswith('.txt'):
        return 'txt'
    
    # Check for patterns in the URL
    if 'pdf' in url_lower:
        return 'pdf'
    elif 'html' in url_lower or 'htm' in url_lower:
        return 'html'
    elif 'article' in url_lower:
        return 'html'  # Most article links are HTML
    elif 'doi.org' in url_lower:
        return 'doi'   # DOI resolver, could be any format
    
    # Default to unknown
    return 'unknown'

def load_index():
    """Load the publication index from the index file."""
    if not os.path.exists(INDEX_FILE):
        return {}
    
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading index file {INDEX_FILE}: {e}")
        return {}

def save_index(index):
    """Save the publication index to the index file."""
    # Ensure the index directory exists
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    
    try:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)
        print(f"Saved index with {len(index)} publications to {INDEX_FILE}.")
    except IOError as e:
        print(f"Error saving index file {INDEX_FILE}: {e}")

def extract_urls_with_metadata(input_filename="publications.txt", output_filename="extracted_urls.txt", 
                              append_mode=True, filter_year=None):
    """
    Reads a tab-separated publication data file, extracts URLs along with comprehensive metadata,
    and writes them to output files for downloading and tracking.
    
    Args:
        input_filename (str): The name of the file to read data from.
        output_filename (str): The name of the file to write extracted data to.
        append_mode (bool): If True, only process new publications not in the index.
        filter_year (int): If provided, only process publications from this year or later.
    """
    # Load existing index
    publication_index = load_index()
    
    # Track new entries
    new_entries = []
    skipped_entries = 0
    metadata_dict = {}
    
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            # Read the first line to get the header
            header_line = f.readline().strip()
            headers = header_line.split('\t')
            
            # Find the indices of the columns we need
            try:
                pub_id_idx = headers.index('pub_id')
                title_idx = headers.index('title')
                authors_idx = headers.index('authors')
                journal_idx = headers.index('journal')
                year_idx = headers.index('year_pub')
                date_idx = headers.index('date_pub') if 'date_pub' in headers else -1
                doi_idx = headers.index('doi')
                url_idx = headers.index('url')
                pubmed_idx = headers.index('pubmed_id') if 'pubmed_id' in headers else -1
                keywords_idx = headers.index('keywords') if 'keywords' in headers else -1
            except ValueError as e:
                print(f"Error: Required column not found in header: {e}")
                return
            
            # Process each line
            for line in f:
                fields = line.strip().split('\t')
                if len(fields) < max(pub_id_idx, title_idx, authors_idx, doi_idx, url_idx) + 1:
                    print(f"Warning: Line has fewer fields than expected, skipping: {line[:50]}...")
                    continue
                
                pub_id = fields[pub_id_idx] if pub_id_idx >= 0 and pub_id_idx < len(fields) else ""
                
                # Skip if this publication is already in the index and we're in append mode
                if append_mode and pub_id in publication_index:
                    skipped_entries += 1
                    continue
                
                title = fields[title_idx] if title_idx >= 0 and title_idx < len(fields) else ""
                authors = fields[authors_idx] if authors_idx >= 0 and authors_idx < len(fields) else ""
                journal = fields[journal_idx] if journal_idx >= 0 and journal_idx < len(fields) else ""
                year = fields[year_idx] if year_idx >= 0 and year_idx < len(fields) else ""
                date_pub = fields[date_idx] if date_idx >= 0 and date_idx < len(fields) else ""
                doi = fields[doi_idx] if doi_idx >= 0 and doi_idx < len(fields) else ""
                url = fields[url_idx] if url_idx >= 0 and url_idx < len(fields) else ""
                pubmed_id = fields[pubmed_idx] if pubmed_idx >= 0 and pubmed_idx < len(fields) else ""
                keywords = fields[keywords_idx] if keywords_idx >= 0 and keywords_idx < len(fields) else ""
                
                # Skip if year filter is applied and this publication is older
                if filter_year and year and int(year) < filter_year:
                    skipped_entries += 1
                    continue
                
                if url and url.startswith('http'):
                    # Extract first author's last name
                    first_author = extract_first_author(authors)
                    
                    # Shorten and clean the title
                    short_title = shorten_title(title)
                    clean_title = clean_text(short_title)
                    
                    # Clean the DOI for filename use
                    clean_doi = clean_text(doi)
                    
                    # Guess the file type
                    file_type = guess_file_type(url)
                    
                    # Create a metadata string for the URL
                    metadata = f"{pub_id}|{clean_doi}|{first_author}|{clean_title}|{file_type}"
                    
                    # Add to entries list
                    new_entries.append((metadata, url))
                    
                    # Store comprehensive metadata
                    metadata_dict[url] = {
                        'pub_id': pub_id,
                        'title': title,
                        'authors': authors,
                        'first_author': first_author,
                        'journal': journal,
                        'year': year,
                        'date_pub': date_pub,
                        'doi': doi,
                        'pubmed_id': pubmed_id,
                        'keywords': keywords,
                        'url': url,
                        'file_type': file_type,
                        'filename_base': f"{clean_doi}_{first_author}_{clean_title}",
                        'processed_date': datetime.now().isoformat()
                    }
                    
                    # Add to index
                    publication_index[pub_id] = {
                        'doi': doi,
                        'title': title,
                        'first_author': first_author,
                        'year': year,
                        'journal': journal,
                        'url': url,
                        'file_type': file_type,
                        'processed_date': datetime.now().isoformat()
                    }
    
    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
        return
    except Exception as e:
        print(f"An error occurred while reading '{input_filename}': {e}")
        return
    
    if new_entries:
        try:
            # Determine write mode based on append_mode
            write_mode = 'a' if append_mode and os.path.exists(output_filename) else 'w'
            
            # Write the URL list with basic metadata
            with open(output_filename, write_mode, encoding='utf-8') as f:
                for metadata, url in new_entries:
                    f.write(f"{metadata}|{url}\n")
                    
            # Also create a backup of the original file in case it needs to be regenerated
            with open(f"{output_filename}.backup", write_mode, encoding='utf-8') as f:
                for metadata, url in new_entries:
                    f.write(f"{metadata}|{url}\n")
            
            # Save the updated index
            save_index(publication_index)
            
            print(f"Successfully extracted {len(new_entries)} new URLs with metadata to '{output_filename}'.")
            print(f"Skipped {skipped_entries} already processed publications.")
            print(f"Updated index saved with {len(publication_index)} total publications.")
            
            # Print file type statistics for new entries
            file_types = {}
            for metadata, url in new_entries:
                file_type = metadata_dict[url]['file_type']
                file_types[file_type] = file_types.get(file_type, 0) + 1
            
            print("\nFile type statistics for new entries:")
            for file_type, count in file_types.items():
                print(f"  {file_type}: {count}")
            
            # Print year statistics
            year_stats = {}
            for url in metadata_dict:
                year = metadata_dict[url].get('year', 'Unknown')
                year_stats[year] = year_stats.get(year, 0) + 1
            
            print("\nYear statistics:")
            for year in sorted(year_stats.keys()):
                print(f"  {year}: {year_stats[year]}")
            
        except Exception as e:
            print(f"An error occurred while writing output files: {e}")
    else:
        if skipped_entries > 0:
            print(f"No new URLs found. Skipped {skipped_entries} already processed publications.")
        else:
            print("No URLs found in the input file.")

def main():
    parser = argparse.ArgumentParser(description='Extract URLs and metadata from publications file.')
    parser.add_argument('--input', type=str, default='publications.txt',
                        help='Input file containing publication data (default: publications.txt)')
    parser.add_argument('--output', type=str, default='extracted_urls.txt',
                        help='Output file for extracted URLs (default: extracted_urls.txt)')
    parser.add_argument('--no-append', action='store_true',
                        help='Process all publications, not just new ones')
    parser.add_argument('--filter-year', type=int,
                        help='Only process publications from this year or later')
    
    args = parser.parse_args()
    
    extract_urls_with_metadata(
        input_filename=args.input,
        output_filename=args.output,
        append_mode=not args.no_append,
        filter_year=args.filter_year
    )

if __name__ == "__main__":
    main()