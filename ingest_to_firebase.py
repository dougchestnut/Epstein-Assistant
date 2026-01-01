import os
import json
import re
import firebase_admin
from firebase_admin import credentials, firestore, storage
import argparse
import mimetypes

# Configuration
CREDENTIALS_PATH = "serviceAccountKey.json"
BUCKET_NAME = "epstein-file-browser.firebasestorage.app"
COL_DOCUMENTS = "documents"
COL_IMAGES = "images"

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
        return firestore.client()

def upload_file_to_storage(local_path, destination_path, content_type=None):
    bucket = storage.bucket()
    blob = bucket.blob(destination_path)
    
    if blob.exists():
        # print(f"Skipping upload: {destination_path} exists.")
        return blob.public_url

    if not content_type:
        content_type, _ = mimetypes.guess_type(local_path)
    
    blob.upload_from_filename(local_path, content_type=content_type)
    blob.make_public()
    print(f"Uploaded: {destination_path}")
    return blob.public_url

def safe_upload(local_path, destination_path, content_type=None):
    """
    Wrapper for upload_file_to_storage that handles network drive instability.
    Returns None if upload fails or file is missing.
    """
    if not os.path.exists(local_path):
        # Double check existence right before upload due to network lag
        return None

    try:
        return upload_file_to_storage(local_path, destination_path, content_type)
    except OSError as e:
        print(f"Network error uploading {local_path}: {e}")
        return None
    except Exception as e:
        print(f"Error uploading {local_path}: {e}")
        return None

def parse_page_num(img_name):
    # e.g. "page11_img1" -> 11
    match = re.search(r'page(\d+)', img_name)
    if match:
        return int(match.group(1))
    return None

def ingest_documents(db, inventory):
    print("\n--- Ingesting Documents ---")
    count = 0
    batch = db.batch()
    batch_count = 0

    for url, meta in inventory.items():
        local_path = meta.get("local_path")
        if not local_path: 
            continue
            
        # We only care about PDFs for the document collection
        if not local_path.lower().endswith('.pdf'):
            continue
            
        # Determine Doc ID from filename stem for consistency
        doc_id = meta.get("id")
        if not doc_id:
             doc_id = os.path.splitext(os.path.basename(local_path))[0]

        # The document folder is where the PDF lives, but our previews are in 
        # epstein_files/DOCNAME/medium.avif
        # Actually, `process_images` outputs to:
        # file_dir/file_stem/medium.avif
        
        file_stem = os.path.splitext(os.path.basename(local_path))[0]
        file_dir = os.path.dirname(local_path)
        output_dir = os.path.join(file_dir, file_stem)
        
        medium_path = os.path.join(output_dir, "medium.avif")
        thumb_path = os.path.join(output_dir, "thumb.avif")
        
        # If we don't have previews, we might still want to ingest the metadata?
        # User said "upload their medium.avif and thumb.avif images".
        # So if they don't exist, we skip or mark as pending. Let's skip for now to keep it clean.
        if not os.path.exists(medium_path):
            continue

        # Upload
        storage_path_m = f"v1/documents/{doc_id}/medium.avif"
        storage_path_t = f"v1/documents/{doc_id}/thumb.avif"
        
        if not os.path.exists(thumb_path):
            continue

        url_m = safe_upload(medium_path, storage_path_m, "image/avif")
        url_t = safe_upload(thumb_path, storage_path_t, "image/avif")
        
        if not url_m or not url_t:
             print(f"Failed to upload previews for {doc_id}, skipping Firestore update.")
             continue
        
        # Data
        doc_data = {
            "title": meta.get("link_text") or file_stem,
            "url": url, # The Direct PDF URL
            "source_page": meta.get("source_page"), # The Web Page URL
            "preview_medium": url_m,
            "preview_thumb": url_t,
            "filename": os.path.basename(local_path),
            "ingested_at": firestore.SERVER_TIMESTAMP
        }
        
        # Upsert
        ref = db.collection(COL_DOCUMENTS).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        batch_count += 1
        count += 1
        
        if batch_count >= 10:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"Committed batch of documents.")

    if batch_count > 0:
        batch.commit()
        
    print(f"Documents Ingested: {count}")

def ingest_images(db, inventory):
    print("\n--- Ingesting Extracted Photos ---")
    count = 0
    batch = db.batch()
    batch_count = 0
    
    for url, meta in inventory.items():
        local_path = meta.get("local_path")
        if not local_path or not local_path.lower().endswith('.pdf'):
            continue
            
        file_stem = os.path.splitext(os.path.basename(local_path))[0]
        file_dir = os.path.dirname(local_path)
        
        # Extracted images are in: epstein_files/DOCID/images/IMGNAME/...
        images_root = os.path.join(file_dir, file_stem, "images")
        
        if not os.path.exists(images_root):
            continue
            
        if not os.path.exists(images_root):
            continue
            
        doc_id = meta.get("id") or file_stem
        
        for img_name in os.listdir(images_root):
            img_dir = os.path.join(images_root, img_name)
            if not os.path.isdir(img_dir):
                continue
                
            # Filter: Check eval.json
            eval_path = os.path.join(img_dir, "eval.json")
            if not os.path.exists(eval_path):
                continue
                
            try:
                with open(eval_path, 'r') as f:
                    eval_data = json.load(f)
                    if not eval_data.get("is_likely_photo"):
                        continue
            except:
                continue

            # Found a photo! Upload previews.
            medium_path = os.path.join(img_dir, "medium.avif")
            thumb_path = os.path.join(img_dir, "thumb.avif")
            
            if not os.path.exists(medium_path):
                continue
                
            storage_path_m = f"v1/images/{doc_id}/{img_name}/medium.avif"
            storage_path_t = f"v1/images/{doc_id}/{img_name}/thumb.avif"
            
            if not os.path.exists(thumb_path):
                continue

            url_m = safe_upload(medium_path, storage_path_m, "image/avif")
            url_t = safe_upload(thumb_path, storage_path_t, "image/avif")
            
            if not url_m or not url_t:
                 continue
            
            # Construct ID
            # "https://.../001.pdf#page11_img1"
            unique_uri = f"{url}#{img_name}"
            
            # Firestore Key (Must be valid path chars)
            # We use doc_id + img_name
            db_id = f"{doc_id}_{img_name}"
            
            # Page Number
            page_num = parse_page_num(img_name)
            
            img_data = {
                "unique_uri": unique_uri,
                "parent_doc_id": doc_id,
                "parent_doc_url": url,
                "source_page_url": meta.get("source_page"),
                "page_num": page_num,
                "preview_medium": url_m,
                "preview_thumb": url_t,
                "image_name": img_name,
                "eval": eval_data,
                "ingested_at": firestore.SERVER_TIMESTAMP
            }
            
            ref = db.collection(COL_IMAGES).document(db_id)
            batch.set(ref, img_data, merge=True)
            batch_count += 1
            count += 1
            
        if batch_count >= 10:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"Committed batch of images.")

    if batch_count > 0:
        batch.commit()

    print(f"Images Ingested: {count}")

def main():
    parser = argparse.ArgumentParser(description="Ingest extracted data to Firebase.")
    parser.add_argument("--only", choices=["documents", "images"], help="Ingest only specific entity type.")
    args = parser.parse_args()

    db = initialize_firebase()
    if not db:
        return
        
    inv_path = "epstein_files/inventory.json"
    if not os.path.exists(inv_path):
        print("Inventory not found.")
        return
        
    with open(inv_path, 'r') as f:
        inventory = json.load(f)
        
    if not args.only or args.only == 'documents':
        ingest_documents(db, inventory)
        
    if not args.only or args.only == 'images':
        ingest_images(db, inventory)

if __name__ == "__main__":
    main()
