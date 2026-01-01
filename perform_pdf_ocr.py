import os
import json
import base64
import requests
import argparse
import io
import fitz  # PyMuPDF
from PIL import Image

# Configuration
LM_STUDIO_URL = "http://192.168.7.142:1234/v1/chat/completions"
MODEL_NAME = "allenai/olmocr-2-7b"
ROOT_DIR = "epstein_files"
TARGET_LONG_SIDE = 1288

SYSTEM_PROMPT = """You are an expert document OCR transcriber. Transcribe the entire page content exactly as Markdown. Preserve:
- Reading order
- Headings (# ## ###)
- Tables (use markdown | syntax)
- Lists (- or 1.)
- Bold/italics if present
- Equations as LaTeX if math
- Layout structure as best as possible
Output ONLY the clean Markdown, no explanations."""

def get_page_image_base64(page):
    """
    Renders a PyMuPDF page to a PNG image with the longest side approx 1288px.
    Returns base64 encoded string.
    """
    # 1. Calculate zoom to get high quality source
    # We want final output ~1288. Let's render at 144dpi (~2.0 scale) or higher first, then downscale cleanly.
    # Default is 72dpi. 
    zoom = 3.0 # High res render
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    # 2. Convert to PIL
    mode = "RGBA" if pix.alpha else "RGB"
    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    if mode == "RGBA":
        img = img.convert("RGB")
        
    # 3. Resize to optimal dimension (1288px max)
    w, h = img.size
    max_dim = max(w, h)
    
    # Check if we need to resize (up or down). 
    # Actually, scaling DOWN is better than starting low and scaling up.
    # We rendered at 3x, so it's likely huge (e.g. 1800-2400+).
    
    if max_dim != TARGET_LONG_SIDE:
        ratio = TARGET_LONG_SIDE / max_dim
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 4. Save as PNG (Lossless)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def perform_ocr_on_page(base64_image, page_num):
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.0 # Strict extraction
        }

        response = requests.post(LM_STUDIO_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        return content

    except Exception as e:
        print(f"Error OCRing page {page_num}: {e}")
        return None

def process_pdf(pdf_path, output_dir, dry_run=False, overwrite=False):
    ocr_path = os.path.join(output_dir, "ocr.md")
    
    if os.path.exists(ocr_path) and not overwrite:
        return

    print(f"Processing PDF: {pdf_path}")
    print(f"  -> Output: {ocr_path}")
    
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            print("Empty PDF.")
            return

        full_transcription = []
        
        for i, page in enumerate(doc):
            page_num = i + 1
            print(f"  - Page {page_num}/{doc.page_count}...", end="", flush=True)
            
            if dry_run:
                print(" [Dry Run]")
                continue

            # Render & OCR
            b64_img = get_page_image_base64(page)
            text = perform_ocr_on_page(b64_img, page_num)
            
            if text:
                full_transcription.append(f"## Page {page_num}\n\n{text}\n\n---\n")
                print(" Done.")
            else:
                full_transcription.append(f"## Page {page_num}\n\n[OCR Failed]\n\n---\n")
                print(" Failed.")

        doc.close()

        if not dry_run and full_transcription:
            with open(ocr_path, "w", encoding="utf-8") as f:
                f.write("\n".join(full_transcription))
            print(f"Saved conversion to {ocr_path}")

    except Exception as e:
        print(f"Failed to process PDF {pdf_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Perform OCR on full PDF documents using LM Studio.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be processed without doing it.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("root_dir", nargs="?", default=ROOT_DIR, help="Root directory to scan.")
    args = parser.parse_args()

    abs_root = os.path.abspath(args.root_dir)
    if not os.path.exists(abs_root):
        print(f"Error: Directory '{abs_root}' not found.")
        return

    print(f"Scanning {abs_root} for PDFs to OCR...")
    
    count = 0
    for root, dirs, files in os.walk(abs_root):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                name_stem = os.path.splitext(file)[0]
                folder_name = os.path.basename(root)
                
                target_dir = None
                
                # Case 1: PDF is inside the document directory (e.g. 001/001.pdf)
                if name_stem == folder_name:
                     target_dir = root
                     
                # Case 2: PDF is a sibling of the document directory (e.g. 001.pdf and 001/ directory exist in same root)
                elif os.path.isdir(os.path.join(root, name_stem)):
                     target_dir = os.path.join(root, name_stem)
                
                # Check validation (must have info.json to be considered a 'document folder')
                if target_dir and os.path.exists(os.path.join(target_dir, "info.json")):
                    process_pdf(pdf_path, target_dir, dry_run=args.dry_run, overwrite=args.overwrite)
                    count += 1
    
    print(f"Finished. Processed {count} PDFs.")

if __name__ == "__main__":
    main()
