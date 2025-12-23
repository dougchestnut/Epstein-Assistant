import os
import json
import warnings
from PIL import Image, ExifTags

# Suppress DecompressionBombWarning if images are very large
warnings.simplefilter('ignore', Image.DecompressionBombWarning)

TARGET_DIR = "epstein_files"
OUTPUT_FILE = "metadata_inventory.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}

def extract_exif(img):
    exif_data = {}
    try:
        exif = img.getexif()
        if exif:
            for k, v in exif.items():
                if k in ExifTags.TAGS:
                    key = ExifTags.TAGS[k]
                else:
                    key = k
                # Handle binary data or non-serializable objects
                if isinstance(v, bytes):
                    try:
                        v = v.decode('utf-8', errors='replace')
                    except:
                        v = str(v)
                exif_data[str(key)] = str(v)
    except Exception as e:
        exif_data["error"] = str(e)
    return exif_data

def extract_xmp(img):
    xmp_data = ""
    try:
        # XMP is often in img.info['XML:com.adobe.xmp']
        # But Pillow doesn't always parse it out neatly.
        # We can also check raw info dict.
        if 'XML:com.adobe.xmp' in img.info:
            xmp_data = img.info['XML:com.adobe.xmp']
        elif 'xmp' in img.info:
            xmp_data = img.info['xmp']
        
        # Some PNGs have it in 'XML:com.adobe.xmp' text chunk
        # Some JPEGs might be handled via raw scan but let's stick to Pillow info first.
        
        # If byte string, decode
        if isinstance(xmp_data, bytes):
            xmp_data = xmp_data.decode('utf-8', errors='replace')
            
    except Exception as e:
        xmp_data = f"Error extracting XMP: {str(e)}"
    return xmp_data

def main():
    abs_target_dir = os.path.abspath(TARGET_DIR)
    
    print(f"Scanning {abs_target_dir} for images...")
    
    count = 0
    saved_count = 0
    for root, dirs, files in os.walk(abs_target_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                file_path = os.path.join(root, file)
                try:
                    with Image.open(file_path) as img:
                        exif = extract_exif(img)
                        xmp = extract_xmp(img)
                        
                        # Only store if we found something meaningful
                        if exif or xmp:
                            # Create directory with same name as image (without extension)
                            file_stem = os.path.splitext(file)[0]
                            # The directory should be in the SAME folder as the image
                            # e.g. root/image_name/
                            target_dir = os.path.join(root, file_stem)
                            os.makedirs(target_dir, exist_ok=True)
                            
                            meta_file_path = os.path.join(target_dir, "meta.json")
                            
                            metadata = {
                                "exif": exif,
                                "xmp": xmp
                            }
                            
                            with open(meta_file_path, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2)
                            saved_count += 1
                        
                        count += 1
                        if count % 1000 == 0:
                            print(f"Processed {count} images... (Saved {saved_count} meta files)")
                except Exception as e:
                    # print(f"Failed to process {file_path}: {e}")
                    pass

    print(f"Finished. Processed {count} images. Created {saved_count} meta.json files.")

if __name__ == "__main__":
    main()
