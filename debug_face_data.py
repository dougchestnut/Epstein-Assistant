
import firebase_admin
from firebase_admin import credentials, firestore
import os

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
try:
    app = firebase_admin.get_app()
except ValueError:
    app = firebase_admin.initialize_app(cred)
db = firestore.client()

# Constants
DOC_ID = "161-09"
IMG_NAME = "page17_img1"
IMG_ID = f"{DOC_ID}_{IMG_NAME}"

print(f"--- Inspecting Image: {IMG_ID} ---")

# Get Image Data
img_ref = db.collection("images").document(IMG_ID)
img_doc = img_ref.get()

if not img_doc.exists:
    print(f"Image {IMG_ID} not found in Firestore.")
else:
    img_data = img_doc.to_dict()
    print("Image Data:")
    print(f"  Preview Medium: {img_data.get('preview_medium')}")
    print(f"  Preview Thumb: {img_data.get('preview_thumb')}")
    
# Get Face Data
faces_ref = db.collection("faces").where("parent_image_id", "==", IMG_ID)
faces_docs = faces_ref.stream()

print("\n--- Faces ---")
for face in faces_docs:
    data = face.to_dict()
    print(f"Face ID: {face.id}")
    print(f"  BBox: {data.get('bbox')}")
    print(f"  Score: {data.get('det_score')}")
