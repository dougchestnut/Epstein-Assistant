
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
