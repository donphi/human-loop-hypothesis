import re
import os

def extract_urls(input_filename="Journals.txt", output_filename="extracted_urls.txt"):
    """
    Reads an input file, extracts URLs starting with 'http', and writes them to an output file.

    Args:
        input_filename (str): The name of the file to read URLs from.
        output_filename (str): The name of the file to write extracted URLs to.
    """
    urls = []
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            content = f.read()
            # Regex to find text starting with "http" followed by non-space characters
            # This pattern captures http, https, etc. and continues until a space or end of line
            urls = re.findall(r'http\S+', content)

    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
        return
    except Exception as e:
        print(f"An error occurred while reading '{input_filename}': {e}")
        return

    if urls:
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                for url in urls:
                    f.write(url + '\n')
            print(f"Successfully extracted {len(urls)} URLs to '{output_filename}'.")
        except Exception as e:
            print(f"An error occurred while writing to '{output_filename}': {e}")
    else:
        print("No URLs found in the input file.")

if __name__ == "__main__":
    extract_urls()