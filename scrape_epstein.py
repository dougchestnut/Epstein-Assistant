import os
import time
import json
import re
import argparse
import requests
import subprocess
from urllib.parse import urljoin, unquote, urlparse
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None

BASE_URL = "https://www.justice.gov/epstein"
SEEDS = [
    "https://www.justice.gov/epstein",
    "https://www.justice.gov/epstein/court-records", 
    "https://www.justice.gov/epstein/foia"
]
OUTPUT_DIR = "epstein_files"
INVENTORY_FILE = "epstein_files/inventory.json"

# Set of visited URLs to avoid cycles
visited_pages = set()
# Inventory of files: url -> metadata
# Inventory of files: url -> metadata
inventory = {}

def load_inventory():
    global inventory
    if os.path.exists(INVENTORY_FILE) and os.path.getsize(INVENTORY_FILE) > 0:
        try:
            with open(INVENTORY_FILE, 'r') as f:
                inventory = json.load(f)
            print(f"Loaded {len(inventory)} items from inventory.")
        except Exception as e:
            print(f"Failed to load inventory: {e}")

def refresh_session(context):
    """
    Refreshes the browser session by navigating to the home page.
    Used when 401 Unauthorized is encountered.
    """
    print("re-authenticating/refreshing session...")
    try:
        page = context.new_page()
        # Apply stealth if available (we assume it's set up in context or we can try importing if needed, 
        # but stealth_sync is global import so we can use it)
        if stealth_sync: stealth_sync(page)
        
        page.goto(BASE_URL, wait_until='domcontentloaded', timeout=45000)
        try:
             page.wait_for_load_state('networkidle', timeout=5000)
        except:
             pass
        time.sleep(5) # Let Akamai/cookies settle
        
        # Check robot check
        content = page.content()
        if "I am not a robot" in content or "Access Denied" in page.title():
             print("Hit robot check during refresh! User interaction may be needed.")
             if True: # We assume we are in headful or at least visible if possible, but automated solving is hard
                  time.sleep(5) 
        
        page.close()
    except Exception as e:
        print(f"Session refresh failed: {e}")


def normalize_url(url):
    return url.split('#')[0]

def is_valid_file_url(url):
    lower_url = url.lower()
    # Common file extensions for documents and media
    valid_exts = ('.pdf', '.zip', '.csv', '.xlsx', '.docx', '.doc', '.xls', '.txt', '.rtf',
                  '.wav', '.mp3', '.mp4', '.mov', '.avi', '.m4a')

    path = urlparse(url).path
    return path.lower().endswith(valid_exts)

def save_inventory():
    with open(INVENTORY_FILE, 'w') as f:
        json.dump(inventory, f, indent=2)

def scrape_page(page, url):
    url = normalize_url(url)
    if url in visited_pages:
        return
    visited_pages.add(url)
    
    print(f"Scraping page: {url}")

    max_retries = 3
    for i in range(max_retries):
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            break
        except Exception as e:
            print(f"Error visiting {url} (Attempt {i+1}/{max_retries}): {e}")
            if i == max_retries - 1:
                return
            time.sleep(2)
            
    # Click known accordions if present to reveal content
    try:
         # Expand all accordions just in case links are hidden
         buttons = page.query_selector_all("button[aria-expanded='false']")
         for btn in buttons:
             if "accordion" in str(btn.get_attribute("class") or ""):
                 btn.click()
                 page.wait_for_timeout(200)
    except Exception:
        pass
        
    # Handle potential Akamai/Robot check
    if "I am not a robot" in page.content():
        print("Detected Robot Check. Please solve it manually if headerless fails...")
        page.wait_for_timeout(5000)



    # Extract all links
    try:
        # Wait a bit for dynamic content
        page.wait_for_timeout(2000)
        links = page.query_selector_all("a")
    except Exception as e:
        print(f"Error extracting links from {url}: {e}")
        return

    page_links = []
    
    for link in links:
        try:
            href = link.get_attribute("href")
            text = link.text_content().strip() if link.text_content() else ""
            
            if not href:
                continue
            
            absolute_url = urljoin(url, href)
            absolute_url = normalize_url(absolute_url)
            
            if is_valid_file_url(absolute_url):
                # It's a file, add to inventory
                if absolute_url not in inventory:
                    print(f"Found file: {text} -> {absolute_url}")
                    # Use found status from known existing entry if possible or just update
                    status = "pending"
                    if absolute_url in inventory and inventory[absolute_url]["status"] == "downloaded":
                         status = "downloaded"
                         
                    inventory[absolute_url] = {
                        "source_page": url,
                        "found_text": text,
                        "status": status,
                        "discovered_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    if "local_path" in inventory.get(absolute_url, {}):
                        inventory[absolute_url]["local_path"] = inventory[absolute_url]["local_path"]
                        
                    save_inventory()
            
            # Navigate to subpages ONLY if they are within the epstein section
            elif absolute_url.startswith("https://www.justice.gov/epstein") and absolute_url not in visited_pages:
                page_links.append(absolute_url)
                
        except Exception as e:
            continue
            
    # Recursively scrape sub-pages
    for sub_url in page_links:
        scrape_page(page, sub_url)

def download_file(context, url, meta):
    print(f"Processing download for: {url}")
    try:
        page = context.new_page()
        if stealth_sync: stealth_sync(page)
        
        # Strategy: Force Browser Download via JS
        # This uses the browser's native networking (so cookies/auth apply) 
        # and streams to disk (via Playwright download manager) rather than buffering in memory.
        
        # 1. Navigate to context page (so cookies apply relative to domain)
        landing_url = meta.get("source_page", BASE_URL)
        try:
            page.goto(landing_url, wait_until='domcontentloaded', timeout=45000)
        except Exception as e_nav:
            print(f"Navigation to source page warning: {e_nav}")
            
        # 2. Trigger Download
        with page.expect_download(timeout=1200000) as download_info: # 20 mins timeout for download start? No, wait, expectation is for START.
            # Actually expect_download waits for the event. The download itself can take longer.
            # But we need to ensure the click happens.
            
            js_code = f"""
                const a = document.createElement('a');
                a.href = "{url}";
                a.download = "{os.path.basename(urlparse(url).path)}"; 
                document.body.appendChild(a);
                a.click();
            """
            page.evaluate(js_code)
            
        download = download_info.value
        
        # Determine filename
        filename = download.suggested_filename
        if not filename or len(filename) < 3:
             filename = os.path.basename(unquote(urlparse(url).path))
             
        # Sanitize and Path
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        filepath = os.path.join(OUTPUT_DIR, filename)

        # Collision check
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filepath):
            new_filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(OUTPUT_DIR, new_filename)
            counter += 1

        print(f"Streaming download to: {filepath}...")
        # Save as (which moves the temporary file)
        download.save_as(filepath)
            
        meta["local_path"] = filepath
        meta["status"] = "downloaded"
        
        # Check size logic if needed, but save_as implies done.
        meta["file_size"] = os.path.getsize(filepath)
        print(f"Downloaded (Browser Stream): {filepath}")
        
        # Attempt Compression
        try:
            compressed_path = compress_media(filepath)
            if compressed_path != filepath:
                meta["local_path"] = compressed_path
                meta["file_size"] = os.path.getsize(compressed_path)
                print(f"Compressed/Processed to: {compressed_path}")
                # Tag as compressed
                if "tags" not in meta: meta["tags"] = []
                if "compressed" not in meta["tags"]: meta["tags"].append("compressed")
        except Exception as comp_e:
            print(f"Compression failed: {comp_e}")
        
        page.close()
        return

    except Exception as e:
        print(f"Download (Browser Stream) failed {url}: {e}")
        # Detect if it was a timeout or a 401 (hard to track exact status in download event)
        # But if we are here, we failed.
        meta["status"] = "failed"
        meta["error"] = str(e)
        try:
            if not page.is_closed(): page.close()
        except: pass
        return

def compress_media(filepath):
    """
    Compresses media files (WAV -> MP3, Video -> smaller MP4) using ffmpeg.
    Returns the new filepath if successful, or the original filepath if not.
    """
    lower_path = filepath.lower()
    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
    if not os.path.exists(ffmpeg_path):
        print(f"ffmpeg not found at {ffmpeg_path}, skipping compression.")
        return filepath
    
    # Audio Compression (WAV -> MP3)
    if lower_path.endswith(".wav"):
        mp3_path = os.path.splitext(filepath)[0] + ".mp3"
        cmd = [
            ffmpeg_path, "-y", "-i", filepath,
            "-codec:a", "libmp3lame", "-qscale:a", "4",
            mp3_path
        ]
        cleanup_original = True
        
    # Video Compression (Re-encode to save space, harmless for already small files?)
    # Only process if not already processed/optimal? 
    # We can check extension or assume if we are called here we want to compress.
    elif lower_path.endswith(('.mov', '.avi', '.m4v')) or (lower_path.endswith('.mp4') and "compressed" not in filepath):
        # We will output as .mp4 with H.264
        # If it's already mp4, we rename output to avoid overwrite collision until success
        base, ext = os.path.splitext(filepath)
        output_path = base + "_compressed.mp4"
        
        # CRF 28 is high compression, acceptable quality for archival. Preset fast.
        # -an removes audio? NO, we want audio. 
        # -c:a aac -b:a 128k
        cmd = [
            ffmpeg_path, "-y", "-i", filepath,
            "-vcodec", "libx264", "-crf", "28", "-preset", "fast",
            "-acodec", "aac", "-b:a", "128k",
            output_path
        ]
        cleanup_original = True
        # If input was mp4, we might replace it.
        
    else:
        return filepath
    
    print(f"Compressing {filepath}...")
    try:
        # Run ffmpeg
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        # Verify output
        target_out = cmd[-1]
        if os.path.exists(target_out) and os.path.getsize(target_out) > 0:
            if cleanup_original:
                os.remove(filepath)
                
            # If we created _compressed.mp4 from .mp4, rename it back to original name?
            # Or keep it to indicate compression. The user wants to save space.
            # If we remove original, we can rename result to original name (if extension matches).
            if lower_path.endswith('.mp4') and target_out.endswith('_compressed.mp4'):
                 os.rename(target_out, filepath)
                 return filepath
            
            return target_out
            
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg failed: {e.stderr.decode()}")
    except Exception as e:
        print(f"Error running ffmpeg: {e}")
        
    return filepath

def main():
    parser = argparse.ArgumentParser(description="Scrape Epstein files from justice.gov")
    parser.add_argument("--no-crawl", action="store_true", help="Skip crawling and only retry failed/pending downloads")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: visible)")
    parser.add_argument("--compress-existing", action="store_true", help="Compress all existing downloaded media files in inventory")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    load_inventory()
    
    # Retroactive compression mode
    if args.compress_existing:
        print("Starting retroactive compression of existing files...")
        count = 0
        for url, meta in inventory.items():
            local_path = meta.get("local_path")
            if local_path and os.path.exists(local_path):
                # Skip if already looks compressed (mp3) unless it's a video we want to re-encode (but let's avoid loop)
                # Simple check: if it's wav or raw video
                if local_path.lower().endswith(('.wav', '.mov', '.avi')) or (local_path.lower().endswith('.mp4') and "compressed" not in meta.get("tags", [])):
                    print(f"Checking {local_path}...")
                    new_path = compress_media(local_path)
                    if new_path != local_path:
                        meta["local_path"] = new_path
                        meta["file_size"] = os.path.getsize(new_path)
                        # Mark as compressed to avoid re-doing MP4s
                        if "tags" not in meta: meta["tags"] = []
                        if "compressed" not in meta["tags"]: meta["tags"].append("compressed")
                        count += 1
                        
                        # Save periodically
                        if count % 5 == 0: save_inventory()
        
        save_inventory()
        print(f"Retroactive compression complete. Processed {count} files.")
        return

        
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            accept_downloads=True
        )
        
        # Step 1: Crawl
        if not args.no_crawl:
            print("Starting crawl...")
            page = context.new_page()
            if stealth_sync:
                stealth_sync(page)
                
            for seed in SEEDS:
                 scrape_page(page, seed)
                 
            page.close()
            print(f"Crawl complete. Found {len(inventory)} items.")
        else:
            print("Skipping crawl (--no-crawl set). Using existing inventory.")
            # Warm up context to avoid 401s on protected files
            print("Warming up browser context...")
            page = context.new_page()
            if stealth_sync: stealth_sync(page)
            try:
                page.goto(BASE_URL, wait_until='domcontentloaded', timeout=45000)
                try:
                    page.wait_for_load_state('networkidle', timeout=5000)
                except:
                    pass
                time.sleep(3) # Let Akamai/cookies settle
                # Check robot
                if "I am not a robot" in page.content() or "Access Denied" in page.title():
                    print("!!! Detected Robot Check or Access Issue. !!!")
                    if not args.headless:
                        print("Please interact with the browser window to solve the CAPTCHA.")
                        input("Press Enter here once you have solved it and the page loads...")
                    else:
                        print("Running in headless mode - cannot solve CAPTCHA interactively.")
                        print("Attempting to proceed anyway, but downloads may fail (401/403).")
                        time.sleep(5)
            except Exception as e:
                print(f"Warmup failed: {e}")
            page.close()

        
        print(f"Crawl complete. Found {len(inventory)} files.")
        
        # Step 2: Download
        print("Starting downloads...")
        for url, meta in inventory.items():
            # Check if already marked downloaded
            if meta.get("status") == "downloaded":
                continue

            # Check if file actually exists on disk even if status says otherwise
            local_path = meta.get("local_path")
            if local_path and os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                print(f"File exists locally, updating status: {local_path}")
                meta["status"] = "downloaded"
                continue
            
            if meta.get("status") == "failed":
                # Clear error to retry
                meta["status"] = "pending"
                print(f"Retrying previously failed item: {url}")
            
            download_file(context, url, meta)
            save_inventory()
            time.sleep(1)
            
        browser.close()

if __name__ == "__main__":
    main()
