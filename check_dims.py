
import json
import os

start_path = "epstein_files/161-09/images/page17_img1/"

for name in ["eval.json", "analysis.json", "info.json"]:
    path = os.path.join(start_path, name)
    if os.path.exists(path):
        print(f"--- {name} ---")
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                # Print top level keys or specific fields
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"{name}: Not found")
