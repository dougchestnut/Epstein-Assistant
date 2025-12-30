import os
import json
import base64
import requests
import argparse

# Configuration
#LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LM_STUDIO_URL = "http://192.168.7.142:1234/v1/chat/completions"
MODEL_NAME = "allenai/olmocr-2-7b"
ROOT_DIR = "epstein_files"

from PIL import Image
import io

def get_base64_encoded_image(image_path):
    # Convert to JPEG for consistency and API compatibility
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        # Resize if too large (max 2048px on longest side) to avoid 400 errors or context limits
        max_dim = 2048
        if max(img.width, img.height) > max_dim:
             ratio = max_dim / max(img.width, img.height)
             new_size = (int(img.width * ratio), int(img.height * ratio))
             img = img.resize(new_size, Image.Resampling.LANCZOS)
             # print(f"Resized {image_path} to {new_size}")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

def perform_ocr(image_path):
    try:
        base64_image = get_base64_encoded_image(image_path)
        
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
                            "text": "Extract and transcribe all visible text from this image as accurately as possible, line by line, including any handwritten parts. Preserve reading order and structure."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 2000 
        }

        response = requests.post(LM_STUDIO_URL, headers=headers, json=payload)
        response.raise_for_status() # Raise an error for bad status codes
        
        result = response.json()
        return result['choices'][0]['message']['content']

    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Server response: {e.response.text}")
        return None

def process_directory(directory, dry_run=False):
    analysis_path = os.path.join(directory, "analysis.json")
    if not os.path.exists(analysis_path):
        return

    try:
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON at {analysis_path}. Skipping.")
        return

    if not analysis.get("needs_ocr", False):
        return

    ocr_path = os.path.join(directory, "ocr.txt")
    if os.path.exists(ocr_path):
        # Already processed
        return

    # Look for image
    # Priority 1: Original image in parent directory with same basename
    dir_name = os.path.basename(directory)
    parent_dir = os.path.dirname(directory)
    
    image_path = None
    
    # Check parent for original
    for ext in [".png", ".jpg", ".jpeg"]:
        candidate = os.path.join(parent_dir, dir_name + ext)
        if os.path.exists(candidate):
            image_path = candidate
            break
            
    # Priority 2: full.avif in current directory
    if not image_path:
        avif_path = os.path.join(directory, "full.avif")
        if os.path.exists(avif_path):
            image_path = avif_path

    if not image_path:
         print(f"Image not found for {directory}, skipping.")
         return

    print(f"Processing: {image_path}")
    
    if dry_run:
        return

    transcription = perform_ocr(image_path)
    
    if transcription:
        with open(ocr_path, "w", encoding='utf-8') as f:
            f.write(transcription)
        print(f"Saved OCR to {ocr_path}")
    else:
        print(f"Failed to get transcription for {image_path}")

def main():
    parser = argparse.ArgumentParser(description="Walk directory and perform OCR on images needing it.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be processed without doing it.")
    parser.add_argument("root_dir", nargs="?", default=ROOT_DIR, help="Root directory to scan.")
    args = parser.parse_args()

    # Verify root exists
    if not os.path.exists(args.root_dir):
        print(f"Error: Directory '{args.root_dir}' not found.")
        return

    for root, dirs, files in os.walk(args.root_dir):
        # Check if this directory looks like an image directory (contains analysis.json)
        if "analysis.json" in files:
             process_directory(root, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
