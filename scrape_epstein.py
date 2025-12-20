import os
import time
import json
import re
import argparse
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
INVENTORY_FILE = "inventory.json"

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
        # Apply stealth if possible (though we did it on context level? stealth_sync needs page)
        if stealth_sync:
            stealth_sync(page)
            
        with page.expect_download(timeout=30000) as download_info:
            try:
                response = page.goto(url, wait_until='commit', timeout=30000)
                # Check for PDF viewer etc...
            except Exception:
                pass
        
        download = download_info.value
        filename = os.path.basename(unquote(urlparse(url).path))
        if not filename or len(filename) < 3:
             filename = f"file_{int(time.time())}.dat"
        
        # Sanitize
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        filepath = os.path.join(OUTPUT_DIR, filename)

        # Avoid Overwrite loop - find a unique filename
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filepath):
            # If the file exists, we need to check if it's the same file?
            # Since we only call download_file for URLs not marked as 'downloaded',
            # existence here likely means a collision with a DIFFERENT url (or a previous unrecorded run).
            # We will generate a new name to be safe.
            new_filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(OUTPUT_DIR, new_filename)
            counter += 1

        download.save_as(filepath)
            
        meta["local_path"] = filepath
        meta["status"] = "downloaded"
        print(f"Downloaded: {filepath}")
        
        page.close()
        return

    except Exception as e:
        # Fallback to in-page fetch (solves 401 errors by using browser context)
        try:
             # We might need to navigate to the URL first or just fetch from about:blank if CORS allows
             # Best bet: navigate to the file URL. If it opens in browser (e.g. video player), we can fetch it.
             # If it triggers download, our expect_download would have caught it.
             # So we assume it opened in the browser.
             
             if page.is_closed():
                 page = context.new_page()
                 if stealth_sync: stealth_sync(page)

             # Navigate and wait for load. 
             # If it's a media file, it might load a player.
             try:
                page.goto(url, timeout=30000, wait_until="mask")
             except:
                pass
             
             # Fetch data as base64 using browser context
             print(f"Attempting in-page fetch for {url}")
             data_b64 = page.evaluate(r"""async (url) => {
                const response = await fetch(url);
                if (response.status !== 200) {
                    throw new Error("Status " + response.status);
                }
                const blob = await response.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
             }""", url)
             
             # data_b64 is like "data:video/mp4;base64,AAAA..."
             header, encoded = data_b64.split(",", 1)
             import base64
             file_data = base64.b64decode(encoded)
             
             filename = os.path.basename(unquote(urlparse(url).path))
             filename = re.sub(r'[^\w\-_\.]', '_', filename)
             filepath = os.path.join(OUTPUT_DIR, filename)

             # Check collision
             base, ext = os.path.splitext(filename)
             counter = 1
             while os.path.exists(filepath):
                 new_filename = f"{base}_{counter}{ext}"
                 filepath = os.path.join(OUTPUT_DIR, new_filename)
                 counter += 1
                 
             with open(filepath, 'wb') as f:
                 f.write(file_data)
                 
             meta["local_path"] = filepath
             meta["status"] = "downloaded"
             print(f"Downloaded (In-Page Fetch): {filepath}")
             page.close()
             
        except Exception as e2:
             print(f"Download failed {url}: {e2}")
             meta["status"] = "failed"
             meta["error"] = str(e2)
             if not page.is_closed():
                 page.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape Epstein files from justice.gov")
    parser.add_argument("--no-crawl", action="store_true", help="Skip crawling and only retry failed/pending downloads")
    args = parser.parse_args()

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    load_inventory()

        
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
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

        
        print(f"Crawl complete. Found {len(inventory)} files.")
        
        # Step 2: Download
        print("Starting downloads...")
        for url, meta in inventory.items():
            if meta.get("status") == "downloaded":
                continue
            
            if meta.get("status") == "failed":
                print(f"Retrying previously failed item: {url}")
            
            download_file(context, url, meta)
            save_inventory()
            time.sleep(1)
            
        browser.close()

if __name__ == "__main__":
    main()
