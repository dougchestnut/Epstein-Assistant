import os
import sys
import json
import argparse
from PIL import Image
import pillow_heif
import fitz # PyMuPDF

# Register AVIF opener
pillow_heif.register_heif_opener()

# Extensions to scan for
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.webp'}
TARGET_DIR = 'epstein_files'

# Define target widths for derivatives
# "full" will be the original size
SIZES = {
    'tiny': 64,
    'thumb': 128,
    'small': 512,
    'medium': 800
}

def create_derivatives(file_path, overwrite=False):
    file_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    file_stem = os.path.splitext(file_name)[0]
    
    output_dir = os.path.join(file_dir, file_stem)
    full_path = os.path.join(output_dir, "full.avif")

    # Skip if already processed and not overwriting
    if os.path.exists(full_path):
        if not overwrite:
            return False
        else:
             print(f"Warning: Overwriting {file_stem}", flush=True)

    try:
        with Image.open(file_path) as img:
            # We must convert to RGB for AVIF if it's not already (e.g. RGBA or P)
            # AVIF supports transparency, but let's be safe standardizing if issues arise. 
            # Pillow's AVIF encoder supports RGBA.
            
            os.makedirs(output_dir, exist_ok=True)
            
            # 1. Save Full (Optimized AVIF)
            # 1. Save Full (Optimized AVIF)
            img.save(full_path, "AVIF", quality=60, speed=6)
            print(f"Generated: {full_path}", flush=True)
            
            # 2. Save Resized Versions
            original_width, original_height = img.size
            aspect_ratio = original_height / original_width
            
            for name, width in SIZES.items():
                if width >= original_width:
                    # If target width is larger than original, just save original as that version?
                    # Or skip? User said "make a ... version". 
                    # Usually better to not upscale, but for consistency let's just use original 
                    # if checking "full" size logic, OR just copy the full one.
                    # Let's simple check: if desired width > original, use original dimensions
                    target_width = original_width
                    target_height = original_height
                else:
                    target_width = width
                    target_height = int(width * aspect_ratio)
                
                resized_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                out_path = os.path.join(output_dir, f"{name}.avif")
                out_path = os.path.join(output_dir, f"{name}.avif")
                resized_img.save(out_path, "AVIF", quality=60, speed=6)
                print(f"Generated: {out_path}", flush=True)
                
            return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def process_pdf(file_path, metadata=None, overwrite=False):
    file_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    file_stem = os.path.splitext(file_name)[0]
    output_dir = os.path.join(file_dir, file_stem)
    
    # Check if done. Use info.json as the flag for new style PDF completion
    if os.path.exists(os.path.join(output_dir, "info.json")):
        if not overwrite:
            return False
        else:
            print(f"Warning: Overwriting output for {file_name}", flush=True)

    try:
        if os.path.getsize(file_path) == 0:
            print(f"Skipping empty PDF: {file_path}", flush=True)
            return False

        print(f"Processing PDF: {file_path}", flush=True)
        doc = fitz.open(file_path)
        if doc.page_count == 0:
            return False
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Page 1 Only for Medium
        TARGET_WIDTH = 800
        page = doc[0]
        
        # Matrix for scaling
        mat = fitz.Matrix(TARGET_WIDTH / page.rect.width, TARGET_WIDTH / page.rect.width)
        pix = page.get_pixmap(matrix=mat)
        
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        if mode == "RGBA":
            img = img.convert("RGB")
        
        img.save(os.path.join(output_dir, "medium.avif"), "AVIF", quality=60, speed=6)
        print(f"Generated: {os.path.join(output_dir, 'medium.avif')}", flush=True)

        
        # 2. Small & Thumb (Page 1 Only)
        page0 = doc[0]
        # Small - 512
        mat_small = fitz.Matrix(512 / page0.rect.width, 512 / page0.rect.width)
        pix_small = page0.get_pixmap(matrix=mat_small)
        img_small = Image.frombytes("RGBA" if pix_small.alpha else "RGB", [pix_small.width, pix_small.height], pix_small.samples).convert("RGB")
        img_small.save(os.path.join(output_dir, "small.avif"), "AVIF", quality=60, speed=6)
        print(f"Generated: {os.path.join(output_dir, 'small.avif')}", flush=True)
        
        # Thumb - 128
        img_thumb = img_small.resize((128, int(128 * img_small.height / img_small.width)), Image.Resampling.LANCZOS)
        img_thumb.save(os.path.join(output_dir, "thumb.avif"), "AVIF", quality=60, speed=6)
        print(f"Generated: {os.path.join(output_dir, 'thumb.avif')}", flush=True)
        
        # 3. Write Info JSON
        if metadata:
            # Add page count
            metadata["page_count"] = doc.page_count
            with open(os.path.join(output_dir, "info.json"), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            print(f"Generated: {os.path.join(output_dir, 'info.json')}", flush=True)
        
        doc.close()
        return True

    except Exception as e:
        print(f"Error processing PDF {file_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Process images and PDFs to generate AVIF derivatives.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--just", choices=["documents", "extracted"], help="Process only specific type (documents=PDFs, extracted=images).")
    args = parser.parse_args()

    abs_target_dir = os.path.abspath(TARGET_DIR)

    # Load Inventory for PDF metadata
    inventory_path = os.path.join(abs_target_dir, 'inventory.json')
    inventory_map = {} # path -> meta
    if os.path.exists(inventory_path):
        try:
            with open(inventory_path, 'r', encoding='utf-8') as f:
                inv = json.load(f)
                for url, meta in inv.items():
                    lp = meta.get("local_path")
                    if lp:
                         inventory_map[os.path.abspath(lp)] = meta
            print(f"Loaded {len(inventory_map)} items from inventory.")
        except Exception as e:
            print(f"Error loading inventory: {e}")

    print(f"Scanning {abs_target_dir} for images to process...", flush=True)
    
    count = 0
    success_count = 0
    
    for root, dirs, files in os.walk(abs_target_dir):
        # We need to be careful not to process the generated AVIFs if we re-run
        # The script only looks for IMAGE_EXTENSIONS. 
        # But we should probably ignore the 'images/filename' directories we created?
        # Actually our structure is:
        # parent/images/foo.jpg <- source
        # parent/images/foo/meta.json
        # parent/images/foo/tiny.avif
        # So when we recurse, we might find foo.jpg again.
        # But we might also eventually scan inside 'foo/' if we are not careful.
        # 'foo/' directory contains .json and .avif. .avif is not in IMAGE_EXTENSIONS (yet? I didn't add it to list).
        # Correct, I did not add .avif to IMAGE_EXTENSIONS, so we won't process outputs.
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                if args.just == 'documents':
                    continue

                file_path = os.path.join(root, file)
                
                # Optional: Print current file being processed (verbose)
                # print(f"Processing: {file}", flush=True)
                
                if create_derivatives(file_path, overwrite=args.overwrite):
                    success_count += 1
            
            elif ext == '.pdf':
                if args.just == 'extracted':
                    continue

                file_path = os.path.join(root, file)
                # Lookup metadata
                meta = inventory_map.get(os.path.abspath(file_path))
                if not meta:
                    # Try fuzzy matching or relative path if needed, but abs path should work
                    pass

                if process_pdf(file_path, metadata=meta, overwrite=args.overwrite):
                    success_count += 1
                
                count += 1
                
                # Update progress every 10 images for better feedback
                if count % 10 == 0:
                    print(f"Processed {count} images... ({success_count} successful). Last: {file}", flush=True)

    print(f"Finished. Processed {count} images. Successfully generated derivatives for {success_count}.", flush=True)

if __name__ == "__main__":
    main()
