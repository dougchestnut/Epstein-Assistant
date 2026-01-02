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
STATE_FILE = "epstein_files/ingest_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"documents": {}, "images": {}}
    return {"documents": {}, "images": {}}

def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save state: {e}")

def get_max_mtime(paths):
    max_mtime = 0
    for p in paths:
        if os.path.exists(p):
            mtime = os.path.getmtime(p)
            if mtime > max_mtime:
                max_mtime = mtime
    return max_mtime

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

def ingest_documents(db, inventory, state, force=False):
    print("\n--- Ingesting Documents ---")
    count = 0
    skipped_count = 0
    batch = db.batch()
    batch_count = 0
    
    doc_state = state.get("documents", {})
    pending_updates = {}

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
            
        # Check freshness EARLY to skip uploads
        # Relevant files for a document include:
        # - The PDF itself (local_path)
        # - The previews (medium, thumb)
        # - The content/ocr text files
        # - The info.json
        
        info_path = os.path.join(output_dir, "info.json")
        
        check_paths = [local_path, medium_path, thumb_path, info_path]
        for name in ["content.txt", "content.md", "ocr.txt", "ocr.md"]:
             check_paths.append(os.path.join(output_dir, name))
             
        current_mtime = get_max_mtime(check_paths)
        last_mtime = doc_state.get(doc_id, 0)
        
        if not force and current_mtime <= last_mtime:
            skipped_count += 1
            continue

        # Upload
        storage_path_m = f"v1/documents/{doc_id}/medium.avif"
        storage_path_t = f"v1/documents/{doc_id}/thumb.avif"
        
        if not os.path.exists(thumb_path):
            continue

        url_m = safe_upload(medium_path, storage_path_m, "image/avif")
        url_t = safe_upload(thumb_path, storage_path_t, "image/avif")
        
        # Text/Markdown Integration
        content_map = {}
        ocr_map = {}
        
        for name in ["content.txt", "content.md", "ocr.txt", "ocr.md"]:
             local_f = os.path.join(output_dir, name)
             if os.path.exists(local_f):
                 storage_f = f"v1/documents/{doc_id}/{name}"
                 # Use text/plain or text/markdown
                 ctype = "text/markdown" if name.endswith(".md") else "text/plain"
                 url_f = safe_upload(local_f, storage_f, ctype)
                 
                 if url_f:
                     if name.startswith("content"):
                         key = "markdown_url" if name.endswith(".md") else "text_url"
                         content_map[key] = url_f
                     elif name.startswith("ocr"):
                         key = "markdown_url" if name.endswith(".md") else "text_url"
                         ocr_map[key] = url_f
        
        if not url_m or not url_t:
             print(f"Failed to upload previews for {doc_id}, skipping Firestore update.")
             continue
        
        # Doc Info Data
        # info_path defined above
        info_data = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r') as f:
                    info_data = json.load(f)
            except: pass
            
        # Data
        doc_data = {
            "title": meta.get("link_text") or file_stem,
            "url": url, # The Direct PDF URL
            "source_page": meta.get("source_page"), # The Web Page URL
            "preview_medium": url_m,
            "preview_thumb": url_t,
            "filename": os.path.basename(local_path),
            "content": content_map,
            "ocr": ocr_map,
            "info": info_data,
            "ingested_at": firestore.SERVER_TIMESTAMP
        }
        
        # Upsert
        ref = db.collection(COL_DOCUMENTS).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        batch_count += 1
        count += 1
        
        # Track pending update
        pending_updates[doc_id] = current_mtime
        
        if batch_count >= 10:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"Committed batch of documents.")
            
            doc_state.update(pending_updates)
            pending_updates = {}

    if batch_count > 0:
        batch.commit()
        doc_state.update(pending_updates)
    
    # Save state back to main dict (in memory mainly, but good practice)
    state["documents"] = doc_state
        
    print(f"Documents Ingested: {count} (Skipped: {skipped_count})")

def ingest_images(db, inventory, state, force=False):
    print("\n--- Ingesting Extracted Photos ---")
    count = 0
    skipped_count = 0
    batch = db.batch()
    batch_count = 0
    
    img_state = state.get("images", {})
    
    pending_updates = {}
    
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
            analysis_path = os.path.join(img_dir, "analysis.json")
            
            if not os.path.exists(medium_path):
                continue

            # Check freshness EARLY
            check_paths = [medium_path, thumb_path, analysis_path, eval_path]
            for name in ["ocr.txt", "ocr.md"]:
                 check_paths.append(os.path.join(img_dir, name))
                 
            current_mtime = get_max_mtime(check_paths)
            
            # Construct DB ID early for state check
            db_id = f"{doc_id}_{img_name}"
            last_mtime = img_state.get(db_id, 0)
            
            if not force and current_mtime <= last_mtime:
                skipped_count += 1
                continue
                
            storage_path_m = f"v1/images/{doc_id}/{img_name}/medium.avif"
            storage_path_t = f"v1/images/{doc_id}/{img_name}/thumb.avif"
            
            if not os.path.exists(thumb_path):
                continue

            url_m = safe_upload(medium_path, storage_path_m, "image/avif")
            url_t = safe_upload(thumb_path, storage_path_t, "image/avif")

            # Text/Markdown Integration for Images
            ocr_map = {}
            for name in ["ocr.txt", "ocr.md"]:
                 local_f = os.path.join(img_dir, name)
                 if os.path.exists(local_f):
                     storage_f = f"v1/images/{doc_id}/{img_name}/{name}"
                     ctype = "text/markdown" if name.endswith(".md") else "text/plain"
                     url_f = safe_upload(local_f, storage_f, ctype)
                     if url_f:
                         key = "markdown_url" if name.endswith(".md") else "text_url"
                         ocr_map[key] = url_f

            # Analysis Data
            # analysis_path defined above
            analysis_data = {}
            if os.path.exists(analysis_path):
                try: 
                    with open(analysis_path, 'r') as f:
                        analysis_data = json.load(f)
                except: pass # analysis_data might be empty
            
            if not url_m or not url_t:
                 continue
            
            # Construct ID
            # "https://.../001.pdf#page11_img1"
            unique_uri = f"{url}#{img_name}"
            
            # Firestore Key (Must be valid path chars)
            # We use doc_id + img_name
            # db_id = f"{doc_id}_{img_name}" # Moved up
            
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
                "ocr": ocr_map,
                "analysis": analysis_data,
                "ingested_at": firestore.SERVER_TIMESTAMP
            }
            
            ref = db.collection(COL_IMAGES).document(db_id)
            batch.set(ref, img_data, merge=True)
            batch_count += 1
            count += 1
            
            # Track pending update
            pending_updates[db_id] = current_mtime
            
            if batch_count >= 10:
                batch.commit()
                batch = db.batch()
                batch_count = 0
                print(f"Committed batch of images.")
                
                img_state.update(pending_updates)
                pending_updates = {}

    if batch_count > 0:
        batch.commit()
        img_state.update(pending_updates)
        
    state["images"] = img_state

    print(f"Images Ingested: {count} (Skipped: {skipped_count})")

def main():
    parser = argparse.ArgumentParser(description="Ingest extracted data to Firebase.")
    parser.add_argument("--only", choices=["documents", "images"], help="Ingest only specific entity type.")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion of all files, ignoring state.")
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
        
    state = load_state()
        
    try:
        if not args.only or args.only == 'documents':
            ingest_documents(db, inventory, state, args.force)
            
        if not args.only or args.only == 'images':
            ingest_images(db, inventory, state, args.force)
    finally:
        save_state(state)

if __name__ == "__main__":
    main()
