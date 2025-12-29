import cv2
import numpy as np
import os
import json
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

INVENTORY_FILE = "epstein_files/inventory.json"

def is_likely_photo(img_path, thresholds=None):
    if thresholds is None:
        thresholds = {
            'min_entropy': 6.5,
            'min_std': 45,
            'min_unique_colors': 15000, # Tuned based on user suggestion (photos >> 10k-20k, docs < 5k-15k)
            'max_lap_var': 150
        }
    
    try:
        logger.debug(f"Reading image: {img_path}")
        img = cv2.imread(img_path)
        if img is None:
            logger.warning(f"Failed to read image: {img_path}")
            return None, {}
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Entropy
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        # Avoid division by zero
        total_pixels = hist.sum()
        if total_pixels == 0:
             logger.warning(f"Image has 0 pixels: {img_path}")
             return None, {}
             
        hist = hist / total_pixels
        hist = hist[hist > 0]
        entropy = -np.sum(hist * np.log2(hist))
        
        # Std dev
        std = np.std(gray)
        
        # Unique colors (fast approx)
        small = cv2.resize(img, (256, 256))
        unique = len(np.unique(small.reshape(-1, 3), axis=0))
        
        # Laplacian variance
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = lap.var()
        
        score_photo = 0
        if entropy > thresholds['min_entropy']:      score_photo += 1
        if std > thresholds['min_std']:              score_photo += 1
        if unique > thresholds['min_unique_colors']: score_photo += 1
        if lap_var < thresholds['max_lap_var']:      score_photo += 1 
        
        # Decision: >= 3 votes = likely photo
        is_photo = score_photo >= 3
        
        stats = {
            "entropy": float(entropy),
            "std_dev": float(std),
            "unique_colors": int(unique),
            "laplacian_var": float(lap_var),
            "score": score_photo,
            "is_likely_photo": is_photo
        }
        
        logger.debug(f"Stats for {img_path}: {stats}")
        return is_photo, stats

    except Exception as e:
        logger.error(f"Error processing {img_path}: {e}", exc_info=True)
        return None, {}

def process_directory(dir_path):
    images_dir = os.path.join(dir_path, "images")
    if not os.path.exists(images_dir):
        # logger.debug(f"No images directory found in {dir_path}")
        return

    # Find all subdirectories in images/ which represent extracted images
    # Structure is usually images/page1_img1/analysis.json
    # We want to place eval.json in images/page1_img1/eval.json
    
    # Also handle the flat images in images/ for reference, 
    # but the goal is to accompany analysis.json which is in the subdir.
    
    # Let's look for subdirectories first.
    items = os.listdir(images_dir)
    image_subdirs = [os.path.join(images_dir, item) for item in items if os.path.isdir(os.path.join(images_dir, item))]
    
    if not image_subdirs:
         # logger.debug(f"No image subdirectories found in {images_dir}")
         pass

    for subdir in image_subdirs:
        # Check if there is a corresponding image file in the parent images_dir
        # The subdir name matches the image name usually (minus extension or preserving it?)
        # Based on README: images/page1_img1.jpg and images/page1_img1/
        
        subdir_name = os.path.basename(subdir)
        
        # Try to find the source image in the images_dir
        # Extensions to check
        extensions = ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp']
        source_image_path = None
        
        for ext in extensions:
            potential_path = os.path.join(images_dir, subdir_name + ext)
            if os.path.exists(potential_path):
                source_image_path = potential_path
                break
            
            # Sometimes the subdir might not match exactly or the extension logic is different.
            # But per README: page1_img1.jpg -> page1_img1/
            
        if not source_image_path:
            logger.warning(f"Could not find source image for subdir {subdir_name} in {images_dir}")
            continue
            
        eval_path = os.path.join(subdir, "eval.json")
        if os.path.exists(eval_path):
            logger.debug(f"Skipping {subdir_name}, eval.json exists.")
            continue # Skip if already processed
            
        # logger.info(f"Processing {subdir_name} -> {source_image_path}")
        is_photo, stats = is_likely_photo(source_image_path)
        
        if stats:
            try:
                with open(eval_path, 'w') as f:
                    json.dump(stats, f, indent=2)
                logger.info(f"Analyzed {subdir_name}: Photo={is_photo} (Score {stats['score']}). Saved to {eval_path}")
            except Exception as e:
                logger.error(f"Failed to save eval.json for {subdir_name}: {e}")
        else:
            logger.warning(f"Could not compute stats for {subdir_name}")


def worker(root_dir, subdir):
    # logger.info(f"Worker starting for {subdir}")
    full_path = os.path.join(root_dir, subdir)
    process_directory(full_path)
    # logger.info(f"Worker finished for {subdir}")

def main():
    parser = argparse.ArgumentParser(description="Filter photos from documents using heuristics")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    epstein_files_dir = "epstein_files"
    if not os.path.exists(epstein_files_dir):
        logger.error(f"Directory {epstein_files_dir} not found.")
        return

    # List all document directories (001, 002, etc.)
    subdirs = [d for d in os.listdir(epstein_files_dir) if os.path.isdir(os.path.join(epstein_files_dir, d))]
    subdirs.sort()
    
    logger.info(f"Found {len(subdirs)} document directories. Starting processing with {args.workers} workers...")
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for subdir in subdirs:
            executor.submit(worker, epstein_files_dir, subdir)
            
    logger.info("All tasks completed.")

if __name__ == "__main__":
    main()
