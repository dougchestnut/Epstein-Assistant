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

def process_pdf(pdf_path, dry_run=False, overwrite=False):
    file_dir = os.path.dirname(pdf_path)
    file_name = os.path.basename(pdf_path)
    ocr_path = os.path.join(file_dir, "ocr.md")
    
    if os.path.exists(ocr_path) and not overwrite:
        return

    print(f"Processing PDF: {pdf_path}")
    
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
    
    # We want to find the PDFs that are inside the ID directories
    # Strategy: Walk logic similar to process_images
    
    for root, dirs, files in os.walk(abs_root):
        for file in files:
            if file.lower().endswith('.pdf'):
                # We typically only want to process the "main" numbered PDF for that folder
                # But actually, users have different structures.
                # Let's just process ANY pdf we find, placing ocr.md next to it.
                # Wait, if we have multiple PDFs in one folder (e.g. 001.pdf and 001_1.pdf),
                # we can't name them ALL 'ocr.md' or we will overwrite.
                # Logic check:
                # If file is '001.pdf', output 'ocr.md' (primary).
                # If file is '001_1.pdf', output '001_1_ocr.md'? 
                # The user request said: "concat ... into an ocr.md file in the documents directory (alongside the content.txt and info.json files)."
                # Usually there is ONE main pdf per folder in this dataset structure (epstein_files/DOCID/DOCID.pdf).
                # But sometimes duplicates exist.
                # Let's look at file structure.
                # If file equals the directory name (e.g. 001/001.pdf), call it ocr.md.
                # If not, call it {filename}_ocr.md to be safe?
                
                pdf_path = os.path.join(root, file)
                
                # Naming Logic
                folder_name = os.path.basename(root)
                name_stem = os.path.splitext(file)[0]
                
                if name_stem == folder_name:
                    # Primary file
                    process_pdf(pdf_path, dry_run=args.dry_run, overwrite=args.overwrite)
                else:
                    # Collateral file? 
                    # For now, let's stick to the user instruction "OCR on the pdf documents themselves".
                    # I will process all of them, but I need to handle the output filename collision if multiple PDFs exist in one dir.
                    # Actually, process_pdf() defines output as `os.path.join(file_dir, "ocr.md")`.
                    # This implies 1 PDF per directory.
                    # If there are multiple, they will fight.
                    # Let's check if the directory *IS* a document directory.
                    
                    # Heuristic: does it have 'info.json'?
                    if os.path.exists(os.path.join(root, "info.json")):
                        # It is a document dir.
                        # Does the PDF match the folder name?
                        if name_stem == folder_name:
                             process_pdf(pdf_path, dry_run=args.dry_run, overwrite=args.overwrite)

if __name__ == "__main__":
    main()
