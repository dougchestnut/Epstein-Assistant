import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, storage
import mimetypes

# Configuration
CREDENTIALS_PATH = "serviceAccountKey.json"  # User needs to provide this
BUCKET_NAME = "epstein-assist.firebasestorage.app" # Placeholder, user needs to update
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
    for url, meta in inventory.items():
        doc_id = meta.get("id") or os.path.basename(meta.get("local_path", "unknown"))
        local_path = meta.get("local_path")
        
        if not local_path or not os.path.exists(local_path):
            print(f"Skipping {doc_id}: Local file not found at {local_path}")
            continue

        # metadata construction
        item_data = {
            "original_url": url,
            "title": meta.get("title") or doc_id,
            "type": "document", # Default to document, adjust based on extension
            "created_at": firestore.SERVER_TIMESTAMP,
            "metadata": meta
        }

        # Upload main file
        file_ext = os.path.splitext(local_path)[1]
        storage_path = f"v1/documents/{doc_id}/original{file_ext}"
        
        # public_url = upload_file_to_storage(local_path, storage_path)
        # item_data["storage_url"] = public_url
        item_data["storage_path"] = storage_path # Store path for client-side usage if needed

        # Prepare images and other analysis artifacts
        # TODO: Scan for generated AVIF images or analysis.json
        
        # Write to Firestore
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc_ref.set(item_data, merge=True)
        print(f"Upserted Firestore doc: {doc_id}")
        count += 1

    print(f"Ingestion complete. Processed {count} items.")

if __name__ == "__main__":
    db = initialize_firebase()
    if db:
        # Placeholder for inventory path - expecting it in the current dir
        ingest_data(db, "inventory.json")
