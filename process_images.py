import os
import sys
from PIL import Image

# Extensions to scan for
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.webp'}
TARGET_DIR = 'epstein_files'

# Define target widths for derivatives
# "full" will be the original size
SIZES = {
    'tiny': 64,
    'thumb': 128,
    'small': 512,
    'medium': 1024
}

def create_derivatives(file_path):
    try:
        with Image.open(file_path) as img:
            # We must convert to RGB for AVIF if it's not already (e.g. RGBA or P)
            # AVIF supports transparency, but let's be safe standardizing if issues arise. 
            # Pillow's AVIF encoder supports RGBA.
            
            # Determine output directory
            # Structure: epstein_files/.../images/page11_img1.jpeg
            # Output:    epstein_files/.../images/page11_img1/tiny.avif, etc.
            
            file_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            file_stem = os.path.splitext(file_name)[0]
            
            output_dir = os.path.join(file_dir, file_stem)
            os.makedirs(output_dir, exist_ok=True)
            
            # 1. Save Full (Optimized AVIF)
            full_path = os.path.join(output_dir, "full.avif")
            img.save(full_path, "AVIF", quality=80, speed=6)
            
            # 2. Save Resized Versions
            original_width, original_height = img.size
            aspect_ratio = original_height / original_width
            
            for name, width in SIZES.items():
                if width >= original_width:
                    # If target width is larger than original, just save original as that version?
                    # Or skip? User said "make a ... version". 
                    # Usually better to not upscale, but for consistency let's just use original 
                    # if checking "full" size logic, OR just copy the full one.
                    # Let's simple check: if desired width > original, use original dimensions
                    target_width = original_width
                    target_height = original_height
                else:
                    target_width = width
                    target_height = int(width * aspect_ratio)
                
                resized_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                out_path = os.path.join(output_dir, f"{name}.avif")
                resized_img.save(out_path, "AVIF", quality=80, speed=6)
                
            return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    abs_target_dir = os.path.abspath(TARGET_DIR)
    print(f"Scanning {abs_target_dir} for images to process...")
    
    count = 0
    success_count = 0
    
    for root, dirs, files in os.walk(abs_target_dir):
        # We need to be careful not to process the generated AVIFs if we re-run
        # The script only looks for IMAGE_EXTENSIONS. 
        # But we should probably ignore the 'images/filename' directories we created?
        # Actually our structure is:
        # parent/images/foo.jpg <- source
        # parent/images/foo/meta.json
        # parent/images/foo/tiny.avif
        # So when we recurse, we might find foo.jpg again.
        # But we might also eventually scan inside 'foo/' if we are not careful.
        # 'foo/' directory contains .json and .avif. .avif is not in IMAGE_EXTENSIONS (yet? I didn't add it to list).
        # Correct, I did not add .avif to IMAGE_EXTENSIONS, so we won't process outputs.
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                file_path = os.path.join(root, file)
                
                if create_derivatives(file_path):
                    success_count += 1
                
                count += 1
                if count % 100 == 0:
                    print(f"Processed {count} images... ({success_count} successful)")

    print(f"Finished. Processed {count} images. Successfully generated derivatives for {success_count}.")

if __name__ == "__main__":
    main()
