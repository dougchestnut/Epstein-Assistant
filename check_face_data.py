
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def check_faces():
    print("Fetching faces...")
    # Get faces
    faces_ref = db.collection("faces").limit(20)
    docs = faces_ref.stream()
    
    for doc in docs:
        data = doc.to_dict()
        print(f"\nFace ID: {doc.id}")
        print(f"  Start 10 chars of keys: {[k for k in data.keys()]}")
        
        bbox = data.get("bbox")
        print(f"  bbox: {bbox} (Type: {type(bbox)})")
        
        embedding = data.get("embedding")
        if embedding:
             # In updated google-cloud-firestore, it might be a Vector object or Map or List
             # If using Vector object from python client, it behaves like a sequence?
             # Let's print type and len
             try:
                 # If it's a Vector object, it might have .to_map() or be iterable
                 # In raw check_face_data, we are using firebase_admin generic client
                 # It might return a Vector object if `ingest` saved it as such.
                 print(f"  embedding type: {type(embedding)}")
                 # If list/tuple
                 if isinstance(embedding, (list, tuple)):
                     print(f"  embedding dim: {len(embedding)}")
                 # If Vector object (it has validation regarding dimension)
                 elif hasattr(embedding, "__len__"):
                     print(f"  embedding dim: {len(embedding)}")
                 elif hasattr(embedding, "value"): # Some Vector wrappers
                     print(f"  embedding dim: {len(embedding.value)}")
             except Exception as e:
                 print(f"  Error checking embedding: {e}")

        parent_id = data.get("parent_image_id")
        doc_title = data.get("doc_title")
        print(f"  parent_image_id: {parent_id}")
        print(f"  doc_title: {doc_title}")
        
        if parent_id:
            parent_doc = db.collection("images").document(parent_id).get()
            if parent_doc.exists:
                p_data = parent_doc.to_dict()
                thumb = p_data.get("preview_thumb")
                med = p_data.get("preview_medium")
                print(f"  Parent exists. Thumb: {'Yes' if thumb else 'No'}, Med: {'Yes' if med else 'No'}")
            else:
                print("  Parent Image DOES NOT EXIST")
        else:
            print("  No parent_image_id field")

if __name__ == "__main__":
    check_faces()
