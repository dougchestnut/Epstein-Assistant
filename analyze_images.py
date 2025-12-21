import os
import json
import base64
import requests
import time

INVENTORY_FILE = "inventory.json"
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "mistralai/ministral-3-3b"

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

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_image(image_path):
    try:
        base64_image = encode_image(image_path)
        
        prompt = (
            "Analyze this image and provide a structured analysis in JSON format.\n"
            "Return a single Valid JSON object with the following keys:\n"
            "- \"type\": one of [\"document\", \"photograph\", \"logo\", \"diagram\", \"other\", \"empty\"]\n"
            "- \"has_faces\": boolean (true if human faces are clearly visible)\n"
            "- \"objects_detected\": list of strings (names of key objects found, empty if none)\n"
            "- \"needs_ocr\": boolean (true if significant text is visible that needs extraction)\n"
            "- \"is_empty\": boolean (true if the image is blank, solid color, or noise)\n"
            "- \"description\": string (a detailed visual description of the content)\n"
            "\nExample Output:\n"
            "{\n"
            "  \"type\": \"document\",\n"
            "  \"has_faces\": false,\n"
            "  \"objects_detected\": [],\n"
            "  \"needs_ocr\": true,\n"
            "  \"is_empty\": false,\n"
            "  \"description\": \"A scanned letter with handwritten signatures.\"\n"
            "}"
        )

        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.7
        }

        response = requests.post(LM_STUDIO_URL, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    except Exception as e:
        print(f"Error analyzing {image_path}: {e}")
        return None

def process_directory(url, meta, overwrite=False):
    extraction_dir = meta.get("extraction_dir")
    if not extraction_dir or not os.path.exists(extraction_dir):
        # Fallback: construct extraction dir from local_path if missing
        local_path = meta.get("local_path")
        if local_path:
            stem = os.path.splitext(os.path.basename(local_path))[0]
            extraction_dir = os.path.join(os.path.dirname(local_path), stem)
    
    if not extraction_dir or not os.path.exists(extraction_dir):
        return

    images_dir = os.path.join(extraction_dir, "images")
    if not os.path.exists(images_dir):
        return

    images = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not images:
        return

    print(f"Found {len(images)} images in {images_dir}")
    
    analyzed_count = 0
    for img_name in images:
        img_path = os.path.join(images_dir, img_name)
        json_path = img_path + ".json"
        
        if os.path.exists(json_path) and not overwrite:
            continue # Already analyzed

        print(f"Analyzing {img_name} with {MODEL}...")
        description = analyze_image(img_path)
        
        if description:
            # Try to find JSON block
            import re
            
            clean_json = None
            
            # Strategy 1: strict markdown code block
            code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', description, re.DOTALL)
            if code_block:
                clean_json = code_block.group(1)
            
            # Strategy 2: loose search for first { and last }
            if not clean_json:
                json_match = re.search(r'\{.*\}', description, re.DOTALL)
                if json_match:
                    clean_json = json_match.group(0)

            if clean_json:
                try:
                    # Validate JSON (and attempt to fix common issues like newlines in strings)
                    # Use a custom decoder/method if strict json.loads fails? 
                    # For now, just strict load. the model output looks valid.
                    json_obj = json.loads(clean_json)
                    with open(json_path, "w") as f:
                        json.dump(json_obj, f, indent=2)
                    print(f"Saved analysis to {json_path}")
                    analyzed_count += 1
                except json.JSONDecodeError as e:
                    print(f"Warning: JSON parse error for {img_name}: {e}. Saving raw response to .txt")
                    with open(img_path + ".txt", "w") as f:
                        f.write(description)
            else:
                 print(f"Warning: No JSON found in response for {img_name}. Saving raw response to .txt")
                 with open(img_path + ".txt", "w") as f:
                    f.write(description)
        
        # Optional sleep to be nice to local GPU if needed
        # time.sleep(0.5)

    if analyzed_count > 0:
        meta["image_analysis_status"] = "partial" if analyzed_count < len(images) else "done"
        update_item(url, meta)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze images using local LLM")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing descriptions")
    args = parser.parse_args()

    print(f"Starting Image Analysis using {MODEL} on {LM_STUDIO_URL}", flush=True)
    if args.overwrite:
        print("Overwrite mode enabled. Existing descriptions will be re-generated.", flush=True)
    
    # Verify LM Studio is up
    try:
        # Simple check - getting models usually works on /v1/models
        requests.get(LM_STUDIO_URL.replace("/chat/completions", "/models"), timeout=5)
    except Exception:
        print("Error: Could not connect to LM Studio. Make sure it is running on port 1234.", flush=True)
        return

    inventory = load_inventory()
    print(f"Loaded {len(inventory)} items.", flush=True)
    
    for url, meta in inventory.items():
        # Process anything downloaded, even if extraction_status isn't fully marked 'done' handled by check
        if meta.get("status") == "downloaded":
             process_directory(url, meta, overwrite=args.overwrite)

    print("Image analysis pass complete.")

if __name__ == "__main__":
    main()
