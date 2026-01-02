import firebase_admin
from firebase_admin import credentials, storage

# Configuration
CREDENTIALS_PATH = "serviceAccountKey.json"
BUCKET_NAME = "epstein-file-browser.firebasestorage.app"

def configure_cors():
    try:
        # Initialize Firebase Admin
        cred = credentials.Certificate(CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred, {
            'storageBucket': BUCKET_NAME
        })

        bucket = storage.bucket()
        
        print(f"Configuring CORS for bucket: {bucket.name}")

        # Define CORS policy
        cors_configuration = [
            {
                "origin": ["*"],  # Allow all origins (or be specific: ["https://your-app.com"])
                "method": ["GET", "HEAD", "OPTIONS"],
                "responseHeader": ["Content-Type", "Access-Control-Allow-Origin"],
                "maxAgeSeconds": 3600
            }
        ]

        # Set CORS policy
        bucket.cors = cors_configuration
        bucket.patch()

        print("CORS configuration updated successfully.")
        print(f"New CORS policy: {bucket.cors}")

    except Exception as e:
        print(f"Error updating CORS configuration: {e}")

if __name__ == "__main__":
    configure_cors()
