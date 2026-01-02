import os
import json
import logging
import argparse
import numpy as np
import cv2
from insightface.app import FaceAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

INVENTORY_FILE = "epstein_files/inventory.json"

def load_inventory():
    try:
        if not os.path.exists(INVENTORY_FILE):
            logging.warning(f"Inventory file not found at {INVENTORY_FILE}")
            return {}
        with open(INVENTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading inventory: {e}")
        return {}

def serialize_face(face):
    """
    Convert an InsightFace object (bunch/dict) to a serializable dictionary.
    """
    # InsightFace returns objects that might need conversion for JSON serialization
    # Common keys: bbox, kps, det_score, landmark_2d_106, gender, age, embedding
    
    data = {}
    
    # Bounding Box
    if 'bbox' in face:
        data['bbox'] = face['bbox'].astype(float).tolist()
    
    # Keypoints (Landmarks)
    if 'kps' in face:
        data['kps'] = face['kps'].astype(float).tolist()
        
    # Detection Score
    if 'det_score' in face:
        data['det_score'] = float(face['det_score'])
        
    # Embedding (normed_embedding usually used for recognition)
    if 'embedding' in face:
        data['embedding'] = face['embedding'].astype(float).tolist()
    elif 'normed_embedding' in face:
        data['embedding'] = face['normed_embedding'].astype(float).tolist()

    # Age and Gender
    if 'age' in face:
        data['age'] = int(face['age'])
    if 'gender' in face:
        data['gender'] = int(face['gender']) # 1 for male, 0 for female usually
        
    return data

def process_image_directory(target_dir, app, overwrite=False):
    """
    Process a single image directory.
    Expects analysis.json to exist in this directory.
    """
    analysis_path = os.path.join(target_dir, "analysis.json")
    faces_path = os.path.join(target_dir, "faces.json")
    
    if not os.path.exists(analysis_path):
        return

    # Check if we should process
    try:
        with open(analysis_path, 'r') as f:
            analysis = json.load(f)
            
        if not analysis.get("has_faces", False):
            return # Skip if no faces reported
            
    except Exception as e:
        logging.error(f"Error reading analysis.json in {target_dir}: {e}")
        return

    # Check if already processed
    if os.path.exists(faces_path) and not overwrite:
        logging.info(f"Skipping {target_dir}, faces.json already exists.")
        return

    # Find the image file
    # The image file is usually not IN the analysis folder but in the parent 'images' folder
    # However, the structure seems to be: 
    # epstein_files/.../images/page1_img1/analysis.json
    #                                    /faces.json
    # AND the actual image source was likely at .../images/page1_img1.jpg OR stored inside?
    # Based on analyze_images.py:
    # img_path = os.path.join(images_dir, img_name)
    # target_dir = os.path.splitext(img_path)[0]
    # So if target_dir is .../images/foo
    # The image is at .../images/foo.jpg or .png etc
    
    # We need to reconstruct the image path.
    # target_dir name is 'foo', parent is 'images'
    parent_dir = os.path.dirname(target_dir)
    base_name = os.path.basename(target_dir)
    
    # Try common extensions
    image_path = None
    for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
        possible_path = os.path.join(parent_dir, base_name + ext)
        if os.path.exists(possible_path):
            image_path = possible_path
            break
            
    if not image_path:
        logging.warning(f"Could not find original image for {target_dir}")
        return

    logging.info(f"Detecting faces in {image_path}...")
    
    try:
        img = cv2.imread(image_path)
        if img is None:
            logging.error(f"Failed to read image {image_path}")
            return
            
        faces = app.get(img)
        
        if not faces:
            logging.info(f"No faces detected by InsightFace in {image_path}")
            # Write empty list to avoid re-processing
            with open(faces_path, 'w') as f:
                json.dump([], f)
            return

        logging.info(f"Found {len(faces)} faces.")
        
        serialized_faces = [serialize_face(face) for face in faces]
        
        with open(faces_path, 'w') as f:
            json.dump(serialized_faces, f, indent=2)
            
    except Exception as e:
        logging.error(f"Error processing {image_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Detect faces in images marked as containing faces.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing faces.json files")
    args = parser.parse_args()

    # Initialize InsightFace
    # accessing standard models - usually downloads to ~/.insightface/models/
    # using 'buffalo_l' as a good default
    try:
        app = FaceAnalysis(name='buffalo_l', root='.insightface') 
        app.prepare(ctx_id=0, det_size=(640, 640)) # ctx_id=0 for GPU, -1 for CPU. Fallback to -1 if no GPU?
        # Actually, let's try to detect if we can use GPU or auto?
        # InsightFace usually fails if we pass 0 and no GPU.
        # Safest for this environment (likely CPU mostly unless user has specific setup) might be -1?
        # Or let's try 0 and catch? 
        # For now, let's assume CPU (-1) to be safe unless we know otherwise.
        # Wait, user is on Mac. Mac M1/M2 might support execution providers for onnxruntime.
        # 'CoreMLExecutionProvider'?
        # Let's stick to CPU for safety in first run.
    except Exception:
        # Retry with CPU
        app = FaceAnalysis(name='buffalo_l', root='.insightface', providers=['CPUExecutionProvider'])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        
    # Re-init strictly for CPU to be safe for this script's stability
    app = FaceAnalysis(name='buffalo_l', root='.insightface', providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    inventory = load_inventory()
    
    # We need to find all "extraction_dir"s or iterate through the structure
    # analyze_images.py logic:
    # 1. iterate inventory items
    # 2. find processed extraction dirs
    # 3. iterate images/ subfolder
    # 4. iterate subfolders of images/ (which are the image_name directories)
    
    count = 0
    for url, meta in inventory.items():
        extraction_dir = meta.get("extraction_dir")
        if not extraction_dir or not os.path.exists(extraction_dir):
            local_path = meta.get("local_path")
            if local_path:
                 stem = os.path.splitext(os.path.basename(local_path))[0]
                 extraction_dir = os.path.join(os.path.dirname(local_path), stem)

        if not extraction_dir or not os.path.exists(extraction_dir):
            continue
            
        images_dir = os.path.join(extraction_dir, "images")
        if not os.path.exists(images_dir):
            continue
            
        # List all subdirectories in images_dir (these are the per-image analysis folders)
        # BUT wait, the analyze script creates: images/foo.jpg AND images/foo/analysis.json
        # So we look for directories.
        
        try:
            candidates = [d for d in os.listdir(images_dir) if os.path.isdir(os.path.join(images_dir, d))]
        except OSError:
            continue
            
        for d in candidates:
            target_dir = os.path.join(images_dir, d)
            process_image_directory(target_dir, app, overwrite=args.overwrite)
            count += 1
            
    logging.info("Face detection pass complete.")

if __name__ == "__main__":
    main()
