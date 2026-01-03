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
COL_FACES = "faces"
STATE_FILE = "epstein_files/ingest_state.json"

# Import Vector for Firestore
try:
    from google.cloud.firestore_v1.vector import Vector
except ImportError:
    print("Warning: Could not import Vector from google.cloud.firestore_v1.vector. Vector search ingestion will fail.")
    Vector = None

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                if "faces" not in state:
                    state["faces"] = {}
                return state
        except:
            return {"documents": {}, "images": {}, "faces": {}}
    return {"documents": {}, "images": {}, "faces": {}}

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
        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = firebase_admin.initialize_app(cred, {
                'storageBucket': BUCKET_NAME
            })
        return firestore.client()
    except ValueError:
        # Fallback if app is already init but client fails? Should not happen with get_app check
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
                    # We accept all analyzed images now, regardless of photo score
                    # if not eval_data.get("is_likely_photo"):
                    #     continue
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

def ingest_faces(db, inventory, state, force=False):
    if not Vector:
        print("\n--- Ingesting Faces (SKIPPED due to missing Vector class) ---")
        return

    print("\n--- Ingesting Faces ---")
    count = 0
    skipped_count = 0
    batch = db.batch()
    batch_count = 0
    
    face_state = state.get("faces", {})
    pending_updates = {}

    # Iterate through extracted images logic again to find faces.json
    for url, meta in inventory.items():
        local_path = meta.get("local_path")
        if not local_path or not local_path.lower().endswith('.pdf'):
            continue
            
        file_stem = os.path.splitext(os.path.basename(local_path))[0]
        file_dir = os.path.dirname(local_path)
        images_root = os.path.join(file_dir, file_stem, "images")
        
        if not os.path.exists(images_root):
             continue
             
        doc_id = meta.get("id") or file_stem
        
        for img_name in os.listdir(images_root):
            img_dir = os.path.join(images_root, img_name)
            if not os.path.isdir(img_dir):
                continue
                
            faces_path = os.path.join(img_dir, "faces.json")
            if not os.path.exists(faces_path):
                continue
                
            current_mtime = os.path.getmtime(faces_path)
            
            # Using doc_id + img_name to track freshness of faces.json processing
            # This is slightly simplified (if faces.json changes, we re-ingest all faces for that image)
            sync_key = f"{doc_id}_{img_name}"
            last_mtime = face_state.get(sync_key, 0)
            
            if not force and current_mtime <= last_mtime:
                # We count skipped faces? Or skipped images?
                # Let's just track we skipped this file
                skipped_count += 1
                continue
            
            try:
                with open(faces_path, 'r') as f:
                    faces_data = json.load(f)
            except Exception as e:
                print(f"Error reading {faces_path}: {e}")
                continue
                
            if not faces_data:
                continue
                
            # We found faces to ingest.
            # Parent Image Reference
            image_db_id = f"{doc_id}_{img_name}"
            
            for i, face in enumerate(faces_data):
                # Face ID: {doc_id}_{img_name}_{i}
                face_id = f"{image_db_id}_{i}"
                
                # Check for embedding
                embedding = face.get("embedding")
                if not embedding:
                    continue

                # Fix nested arrays for Firestore (kps is [[x,y], ...])
                kps = face.get("kps")
                if kps and isinstance(kps, list):
                    # Convert to list of objects: [{'x': 1, 'y': 2}, ...]
                    kps = [{'x': p[0], 'y': p[1]} for p in kps if len(p) >= 2]
                    
                # Store
                face_doc = {
                    "parent_image_id": image_db_id,
                    "parent_doc_id": doc_id,
                    "bbox": face.get("bbox"), # [x1, y1, x2, y2]
                    "det_score": face.get("det_score"),
                    "kps": kps,
                    "embedding": Vector(embedding), # Create Vector object
                    "image_name": img_name,
                    "doc_title": meta.get("link_text") or file_stem,
                    "page_num": parse_page_num(img_name),
                    "ingested_at": firestore.SERVER_TIMESTAMP
                }
                
                ref = db.collection(COL_FACES).document(face_id)
                batch.set(ref, face_doc, merge=True)
                batch_count += 1
                count += 1
                
                if batch_count >= 10:
                    batch.commit()
                    batch = db.batch()
                    batch_count = 0
            
            # Track as updated
            pending_updates[sync_key] = current_mtime
            
            if batch_count >= 10: # Check again after loop
                 batch.commit()
                 batch = db.batch()
                 batch_count = 0
                 
    if batch_count > 0:
        batch.commit()
    
    face_state.update(pending_updates)
    state["faces"] = face_state
    
    print(f"Faces Ingested: {count} (from {len(pending_updates)} images, Skipped {skipped_count} images)")


def main():
    parser = argparse.ArgumentParser(description="Ingest extracted data to Firebase.")
    parser.add_argument("--only", choices=["documents", "images", "faces"], help="Ingest only specific entity type.")
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

        if not args.only or args.only == 'faces':
            ingest_faces(db, inventory, state, args.force)
            
    finally:
        save_state(state)

if __name__ == "__main__":
    main()
