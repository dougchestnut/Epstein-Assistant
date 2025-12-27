
import json
import os
import shutil

INVENTORY_FILE = "inventory.json"
BACKUP_FILE = "inventory.json.corrupted_bak"

def repair():
    if not os.path.exists(INVENTORY_FILE):
        print("No inventory file.")
        return

    # Backup first
    if not os.path.exists(BACKUP_FILE):
        shutil.copy(INVENTORY_FILE, BACKUP_FILE)
        print(f"Backed up to {BACKUP_FILE}")

    with open(INVENTORY_FILE, 'r') as f:
        content = f.read()

    try:
        json.loads(content)
        print("File is actually valid!")
        return
    except json.JSONDecodeError as e:
        print(f"Corrupted at pos {e.pos}: {e}")
        
        # Strategy: The file likely has appended garbage or a cutoff.
        # We will try to find the last valid closing brace sequence.
        # Since it's a dict of dicts, it ends with "  }\n}" or similar.
        
        valid_part = content[:e.pos]
        
        # Naive attempt: find the last comma, remove it, add closing brace?
        # Or if "Extra data", it means we have multiple objects.
        # "Extra data" usually means `} {` or `} ...garbage...`
        
        # If the error is "Extra data", it means parsing succeeded up to a point, but there's more.
        # In that case, we can just take the valid part!
        
        if "Extra data" in str(e):
             # The decoder finished a valid object, but found more.
             # We can just truncate at e.pos
             print("Detected Extra Data error. Truncating to valid JSON.")
             repaired_content = content[:e.pos]
             
             try:
                 data = json.loads(repaired_content)
                 print(f"Recovered {len(data)} items.")
                 with open(INVENTORY_FILE, 'w') as f:
                     json.dump(data, f, indent=2)
                 print("Saved repaired inventory.")
                 return
             except Exception as e2:
                 print(f"Truncation failed: {e2}")

        # Fallback for other errors (like "Expecting value")
        last_comma = valid_part.rfind(',')
        if last_comma == -1:
             print("Could not find comma.")
             return
             
        repaired_content = valid_part[:last_comma] + "\n}"
        try:
            data = json.loads(repaired_content)
            print(f"Recovered {len(data)} items (fallback).")
            with open(INVENTORY_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print("Saved repaired inventory.")
        except Exception as e3:
            print(f"Fallback failed: {e3}")

if __name__ == "__main__":
    repair()
