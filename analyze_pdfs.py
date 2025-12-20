
import json
import os
import random
from pypdf import PdfReader

INVENTORY_FILE = 'inventory.json'
FILES_DIR = 'epstein_files'
SAMPLE_SIZE = 20

def load_inventory():
    with open(INVENTORY_FILE, 'r') as f:
        return json.load(f)

def analyze_pdf(file_path):
    result = {
        'path': file_path,
        'size_bytes': os.path.getsize(file_path),
        'encrypted': False,
        'pages': 0,
        'text_content_found': False,
        'metadata': {},
        'error': None
    }
    
    try:
        reader = PdfReader(file_path)
        result['encrypted'] = reader.is_encrypted
        result['pages'] = len(reader.pages)
        
        # Metadata
        if reader.metadata:
            # Convert to dict and handle potential None values
            result['metadata'] = {k: str(v) for k, v in reader.metadata.items() if v is not None}

        # Check for text on first 3 pages
        text_found = ""
        for i in range(min(3, len(reader.pages))):
            try:
                page_text = reader.pages[i].extract_text()
                if page_text and page_text.strip():
                    text_found += page_text.strip()
            except Exception as e:
                pass # Specific page extraction error
        
        if len(text_found) > 50: # Arbitrary threshold for "meaningful text"
            result['text_content_found'] = True
            
    except Exception as e:
        result['error'] = str(e)
        
    return result

def main():
    print("Loading inventory...")
    inventory = load_inventory()
    
    # Filter for downloaded files
    downloaded_files = [
        info['local_path'] 
        for info in inventory.values() 
        if info.get('status') == 'downloaded' and os.path.exists(info['local_path'])
    ]
    
    print(f"Found {len(downloaded_files)} downloaded files.")
    
    if not downloaded_files:
        print("No downloaded files found to analyze.")
        return

    # Sample standard PDFs (could add checking for different file sizes if needed)
    sample_files = random.sample(downloaded_files, min(SAMPLE_SIZE, len(downloaded_files)))
    
    print(f"Analyzing {len(sample_files)} sample files...\n")
    
    results = []
    for f in sample_files:
        res = analyze_pdf(f)
        results.append(res)
        
        status = "SEARCHABLE" if res['text_content_found'] else "SCANNED/IMAGE"
        if res['error']:
            status = f"ERROR: {res['error']}"
        elif res['encrypted']:
            status = "ENCRYPTED"
            
        print(f"File: {f}")
        print(f"  Size: {res['size_bytes']} bytes")
        print(f"  Pages: {res['pages']}")
        print(f"  Status: {status}")
        if res['metadata']:
            print(f"  Metadata: {res['metadata']}")
        print("-" * 40)

    # Summary
    text_count = sum(1 for r in results if r['text_content_found'])
    print(f"\nSummary:")
    print(f"Total Analyzed: {len(results)}")
    print(f"Text Content Found (Searchable): {text_count}")
    print(f"No Text Content (Likely Scanned): {len(results) - text_count}")

if __name__ == "__main__":
    main()
