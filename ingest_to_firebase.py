import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, storage
import mimetypes

# Configuration
CREDENTIALS_PATH = "serviceAccountKey.json"  # User needs to provide this
BUCKET_NAME = "epstein-file-browser.firebasestorage.app" # Updated to confirmed bucket name
COLLECTION_NAME = "items"

def initialize_firebase():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Error: {CREDENTIALS_PATH} not found. Please place your Firebase Admin SDK private key here.")
        return None
    
    cred = credentials.Certificate(CREDENTIALS_PATH)
    try:
        firebase_admin.initialize_app(cred, {
            'storageBucket': BUCKET_NAME
        })
        return firestore.client()
    except ValueError:
        # App already initialized
        return firestore.client()

def upload_file_to_storage(local_path, destination_path):
    bucket = storage.bucket()
    blob = bucket.blob(destination_path)
    
    # Check if exists
    if blob.exists():
        print(f"Skipping {destination_path} (already exists)")
        return blob.public_url

    content_type, _ = mimetypes.guess_type(local_path)
    blob.upload_from_filename(local_path, content_type=content_type)
    blob.make_public()
    print(f"Uploaded {destination_path}")
    return blob.public_url

def ingest_data(db, inventory_path):
    with open(inventory_path, 'r') as f:
        inventory = json.load(f)

    # Process each item in inventory
    # Structure of inventory is key (url) -> metadata
    
    count = 0

    images_count = 0
    for url, meta in inventory.items():
        doc_id = meta.get("id") or os.path.basename(meta.get("local_path", "unknown"))
        local_path = meta.get("local_path")
        
        if not local_path or not os.path.exists(local_path):
            # print(f"Skipping {doc_id}: Local file not found at {local_path}")
            continue

        # The images are extracted into a folder with the same name as the pdf (minus extension)
        # e.g. epstein_files/doc_id.pdf -> epstein_files/doc_id/images/
        file_stem_path = os.path.splitext(local_path)[0]
        images_dir = os.path.join(file_stem_path, "images")

        if not os.path.exists(images_dir):
            if count % 100 == 0: 
                 print(f"No images directory for {doc_id} at {images_dir} (checking every 100th)")
            continue

        # Iterate over extracted image folders
        for img_name in os.listdir(images_dir):
            img_dir_path = os.path.join(images_dir, img_name)
            if not os.path.isdir(img_dir_path):
                continue

            thumb_path = os.path.join(img_dir_path, "thumb.avif")
            medium_path = os.path.join(img_dir_path, "medium.avif")

            if not os.path.exists(thumb_path):
                continue
            
            # Construct a unique ID for this image item
            # img_name is usually "page1_img1"
            item_id = f"{doc_id}_{img_name}"
            
            # Check for analysis.json
            analysis_path = os.path.join(img_dir_path, "analysis.json")
            analysis_data = {}
            if os.path.exists(analysis_path):
                try:
                    with open(analysis_path, 'r') as af:
                        analysis_data = json.load(af)
                except Exception as e:
                    print(f"Error reading analysis for {item_id}: {e}")

            # Check for eval.json (New)
            eval_path = os.path.join(img_dir_path, "eval.json")
            eval_data = {}
            if os.path.exists(eval_path):
                try:
                    with open(eval_path, 'r') as ef:
                        eval_data = json.load(ef)
                except Exception as e:
                    print(f"Error reading eval for {item_id}: {e}")

            # Base metadata from parent document
            item_data = {
                "original_url": url,
                "title": f"{meta.get('title') or doc_id} - {img_name}",
                "type": "image",
                "created_at": firestore.SERVER_TIMESTAMP,
                "doc_id": doc_id, # Reference to parent
                "image_name": img_name,
                "metadata": meta, # Include original metadata
                "analysis": analysis_data, # Include image analysis (needs_ocr, is_empty, etc)
                "eval": eval_data, # Include evaluation data (is_likely_photo)
                "is_likely_photo": eval_data.get("is_likely_photo", False) # Top-level promotion for easier querying
            }

            # Upload Thumb
            storage_path_thumb = f"v1/images/{doc_id}/{img_name}/thumb.avif"
            public_url_thumb = upload_file_to_storage(thumb_path, storage_path_thumb)
            item_data["thumbnail_url"] = public_url_thumb
            item_data["thumbnail_storage_path"] = storage_path_thumb

            # Upload Medium
            if os.path.exists(medium_path):
                storage_path_medium = f"v1/images/{doc_id}/{img_name}/medium.avif"
                public_url_medium = upload_file_to_storage(medium_path, storage_path_medium)
                item_data["medium_url"] = public_url_medium
                item_data["medium_storage_path"] = storage_path_medium

            # Upsert
            doc_ref = db.collection(COLLECTION_NAME).document(item_id)
            doc_ref.set(item_data, merge=True)
            print(f"Upserted image: {item_id}")
            images_count += 1
        
        count += 1

    print(f"Ingestion complete. Processed {count} documents, created/updated {images_count} image items.")

if __name__ == "__main__":
    db = initialize_firebase()
    if db:
        # Placeholder for inventory path - expecting it in the current dir
        ingest_data(db, "epstein_files/inventory.json")
