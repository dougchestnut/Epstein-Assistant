import os
import json
import fitz  # pymupdf
import pathlib

INVENTORY_FILE = "epstein_files/inventory.json"
OUTPUT_DIR = "epstein_files"

def load_inventory():
    try:
        if not os.path.exists(INVENTORY_FILE):
            return {}
        with open(INVENTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def update_item(url, data):
    inv = load_inventory()
    if url in inv:
        inv[url].update(data)
        with open(INVENTORY_FILE, 'w') as f:
            json.dump(inv, f, indent=2)


def extract_content(url, meta):
    local_path = meta.get("local_path")
    if not local_path or not os.path.exists(local_path):
        return
        
    classification = meta.get("classification")
    if not classification:
        return

    # Create subdirectory
    # e.g. epstein_files/001.pdf -> epstein_files/001/
    filename = os.path.basename(local_path)
    stem = os.path.splitext(filename)[0]
    
    # Clean stem logic if collision occurred e.g. 001_1
    target_dir = os.path.join(OUTPUT_DIR, stem)
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    # Paths for extraction
    text_path = os.path.join(target_dir, "content.txt")
    images_dir = os.path.join(target_dir, "images")
    
    doc = fitz.open(local_path)
    
    # TEXT EXTRACTION
    # Ideally for 'text' or 'mixed'
    if classification in ["text", "mixed", "scanned"]: # Try for all, even scanned might have simple layer
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        
        if full_text.strip():
            with open(text_path, "w") as f:
                f.write(full_text)
                
    # IMAGE EXTRACTION
    # For now, let's extract images if 'mixed' or 'scanned' or explicitly requested
    # We'll do it for all to start, but limit count/size?
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
        
    for i, page in enumerate(doc):
        image_list = page.get_images()
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            image_filename = f"page{i+1}_img{img_index+1}.{image_ext}"
            image_filepath = os.path.join(images_dir, image_filename)
            
            with open(image_filepath, "wb") as f:
                f.write(image_bytes)

    meta["extraction_status"] = "done"
    meta["extraction_dir"] = target_dir
    print(f"Extracted {local_path} to {target_dir}")

def main():
    inventory = load_inventory()
    print(f"Loaded {len(inventory)} items.")
    
    import zipfile
    
    updates = 0
    for url, meta in inventory.items():
        local_path = meta.get("local_path", "")
        if not local_path: 
            continue
            
        is_pdf = local_path.lower().endswith(".pdf")
        is_zip = local_path.lower().endswith(".zip")
        
        if not (is_pdf or is_zip):
            continue

        # Check if processing is needed
        should_process = False
        if meta.get("extraction_status") != "done":
             should_process = True
        else:
             # Check for content.txt (for PDFs) or extraction dir (for ZIPs)
             extraction_dir = meta.get("extraction_dir")
             if extraction_dir and not os.path.exists(extraction_dir):
                 should_process = True
             elif is_pdf and extraction_dir and os.path.exists(extraction_dir):
                 text_path = os.path.join(extraction_dir, "content.txt")
                 if not os.path.exists(text_path):
                     should_process = True
        
        if should_process and meta.get("status") == "downloaded":
             if is_pdf:
                extract_content(url, meta)
             elif is_zip:
                # Extract ZIP
                target_dir = os.path.splitext(local_path)[0]
                try:
                    with zipfile.ZipFile(local_path, 'r') as zip_ref:
                        # Safety: check for malicious paths? For this purpose, basic extractall is likely fine.
                        zip_ref.extractall(target_dir)
                    print(f"Unzipped {local_path} to {target_dir}")
                    
                    meta["extraction_status"] = "done"
                    meta["extraction_dir"] = target_dir
                    update_item(url, meta)
                except Exception as e:
                    print(f"Failed to unzip {local_path}: {e}")
                    
             updates += 1
             
    print("Extraction complete.")


if __name__ == "__main__":
    main()
