import os
import json
import glob

def diagnose():
    root = "epstein_files"
    print(f"Scanning {root} for corrupt faces.json files...")
    
    # Walk the directory tree
    for dirpath, dirnames, filenames in os.walk(root):
        if "faces.json" in filenames:
            path = os.path.join(dirpath, "faces.json")
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    
                faces = []
                if isinstance(data, list):
                    faces = data
                elif isinstance(data, dict):
                    faces = data.get("faces", [])
                
                for i, face in enumerate(faces):
                    if not isinstance(face, dict):
                        print(f"FOUND CORRUPT FILE: {path}")
                        print(f"  Item {i} is type {type(face)}: {face}")
                        return
                        
            except Exception as e:
                print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    diagnose()
