import os
import json
import fitz  # pymupdf

INVENTORY_FILE = "epstein_files/inventory.json"
PDF_DIR = "epstein_files"

def load_inventory():
    try:
        if not os.path.exists(INVENTORY_FILE):
            return {}
        with open(INVENTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def update_item(url, data):
    # Atomic-ish update: load, update one item, save
    # This is slow but safer if scraper is appending
    inv = load_inventory()
    if url in inv:
        inv[url].update(data)
        with open(INVENTORY_FILE, 'w') as f:
            json.dump(inv, f, indent=2)


def analyze_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        page_count = len(doc)
        total_text_len = 0
        total_image_area = 0
        page_area = 0
        
        # Check first few pages to save time? Or all?
        # Let's check up to 5 pages for heuristic
        pages_to_check = min(5, page_count)
        
        for i in range(pages_to_check):
            page = doc.load_page(i)
            text = page.get_text()
            total_text_len += len(text.strip())
            
            # Image area calculation
            images = page.get_images()
            for img in images:
                # This gives us the XREF of the image, not the rect on page necessarily without more work
                # Simpler: just count number of images?
                # Or use page.get_text("dict") to find image blocks.
                pass
        
        doc.close()
        
        # Classification Logic
        # If significant text found, it's TEXT (or searchable)
        # If very little text, it's likely SCANNED/IMAGE
        
        # Threshold: average 50 chars per page?
        avg_text = total_text_len / pages_to_check if pages_to_check > 0 else 0
        
        if avg_text > 50:
            classification = "text"
        else:
            classification = "scanned"
            
        return {
            "page_count": page_count,
            "classification": classification,
            "avg_text_per_page": avg_text
        }
        
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return {"error": str(e), "classification": "error"}

def main():
    inventory = load_inventory()
    print(f"Loaded {len(inventory)} items.")
    
    updates = 0
    for url, meta in inventory.items():
        local_path = meta.get("local_path")
        
        # Skip if already classified or not downloaded
        if meta.get("classification"):
            continue
            
        if meta.get("status") != "downloaded" or not local_path or not os.path.exists(local_path):
            continue
            
        if not local_path.lower().endswith(".pdf"):
            update_item(url, {"classification": "other"})
            updates += 1
            continue

        print(f"Analyzing {local_path}...")
        results = analyze_pdf(local_path)
        
        update_item(url, results)
        updates += 1
        
    print("Classification complete.")


if __name__ == "__main__":
    main()
