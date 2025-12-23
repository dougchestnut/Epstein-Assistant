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
        
        # Determine target directory and file paths
        # e.g. images/foo.jpg -> images/foo/analysis.json
        target_dir = os.path.splitext(img_path)[0]
        os.makedirs(target_dir, exist_ok=True)
        
        json_path = os.path.join(target_dir, "analysis.json")
        txt_path = os.path.join(target_dir, "analysis.txt")
        
        # Migration Logic: Check for old files and move them if new ones don't exist
        old_json_path = img_path + ".json"
        old_txt_path = img_path + ".txt"
        
        if os.path.exists(old_json_path):
            if not os.path.exists(json_path):
                try:
                    os.rename(old_json_path, json_path)
                    print(f"Migrated {old_json_path} -> {json_path}")
                except OSError as e:
                    print(f"Error migrating {old_json_path}: {e}")
            else:
                # New file already exists, just remove the old one or leave it? 
                # Safer to leave it or maybe rename it to .bak? 
                # For now let's just log it.
                print(f"Notice: Both {old_json_path} and {json_path} exist. Keeping new, ignoring old.")

        if os.path.exists(old_txt_path):
            if not os.path.exists(txt_path):
                 try:
                    os.rename(old_txt_path, txt_path)
                    print(f"Migrated {old_txt_path} -> {txt_path}")
                 except OSError as e:
                    print(f"Error migrating {old_txt_path}: {e}")

        # Check if analysis already exists (in new location)
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
                    # Remove comments (// ...)
                    clean_json = re.sub(r'//.*$', '', clean_json, flags=re.MULTILINE)
                    
                    # Fix unescaped newlines within strings.
                    # This is tricky without a full parser, but we can try to escape control chars.
                    # Specialized fix for "description" field having unescaped quotes or Python-style triple quotes
                    # Pattern: "description":\s*("{1,3})((?:.|\n)*?)("{1,3}\s*\}(\s*)?)$
                    def fix_description_quotes(full_json_str):
                        # Matches "description": "..." or "description": """..."""
                        # We capture the opening quote(s), the content, and the closing quote(s) + closing brace
                        pattern = r'("description"\s*:\s*("{1,3}))((?:.|\n)*?)("{1,3}\s*\}(\s*)?)$'
                        match = re.search(pattern, full_json_str, re.DOTALL)
                        if match:
                            prefix_full = match.group(1) # "description": """
                            opener = match.group(2)      # """
                            content = match.group(3)     # content inside
                            suffix_full = match.group(4) # """ }
                            closer = match.group(5)      # """ (part of suffix_full) but we need to match it roughly

                            # We want to replace the opener/closer with a simple single quote "
                            # And we want to escape the content.
                            
                            # Reconstruct prefix with just one quote
                            new_prefix = '"description": "'
                            
                            # Clean content:
                            # 1. Escape backslashes first?
                            # content = content.replace('\\', '\\\\') # Dangerous if already escaped?
                            # 2. Escape double quotes "
                            fixed_content = content.replace('"', '\\"')
                            # 3. Escape newlines
                            fixed_content = fixed_content.replace('\n', '\\n').replace('\r', '')
                            
                            return full_json_str[:match.start()] + new_prefix + fixed_content + '"\n}'
                        return full_json_str

                    clean_json_fixed = fix_description_quotes(clean_json)
                    
                    # Original newline fix logic for other fields (if any), modified to be safer
                    def escape_newlines(match):
                         return match.group(0).replace('\n', '\\n').replace('\r', '')
                    
                    # Apply general newline fix to the whole thing (careful not to double escape description if validation passes)
                    # Actually, if we fixed description, we might have fixed the main culprit.
                    # Let's try parsing.
                    
                    try:
                        json_obj = json.loads(clean_json_fixed)
                    except:
                        # If that failed, try the general newline fix on the *original* string (or the fixed one?)
                        # The regex fix_description_quotes returns the full string with modification.
                        # Run the general newline escaper on top of it?
                         clean_json_fixed_2 = re.sub(r'"((?:[^"\\]|\\.)*)"', escape_newlines, clean_json_fixed, flags=re.DOTALL)
                         json_obj = json.loads(clean_json_fixed_2)
                    with open(json_path, "w") as f:
                        json.dump(json_obj, f, indent=2)
                    print(f"Saved analysis to {json_path}")
                    analyzed_count += 1
                except (json.JSONDecodeError, Exception) as e:
                    # Fallback attempt without sanitization or save as txt
                    try:
                         json_obj = json.loads(clean_json, strict=False)
                         with open(json_path, "w") as f:
                            json.dump(json_obj, f, indent=2)
                         print(f"Saved analysis to {json_path} (strict=False)")
                         analyzed_count += 1
                    except Exception as e2:
                        print(f"Final warning: Could not parse JSON for {img_name}: {e2}. Saving raw response to .txt")
                        with open(txt_path, "w") as f:
                            f.write(description)
            else:
                 print(f"Warning: No JSON found in response for {img_name}. Saving raw response to .txt")
                 with open(txt_path, "w") as f:
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
