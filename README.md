# Epstein Assist

A set of tools to scrape, inventory, and analyze files related to the Jeffrey Epstein case released by the Department of Justice.

## Scraper

The project includes a robust scraping script `scrape_epstein.py` designed to fetch all documents and media files from [https://www.justice.gov/epstein](https://www.justice.gov/epstein).

### Features
*   **Comprehensive Crawl**: Recursively finds files in subsections like Court Records and FOIA (FBI, BOP).
*   **Bot Protection Bypass**: Uses `playwright-stealth` and user-like behavior to navigate Akamai protections.
*   **Resumable**: Maintains a local `inventory.json` database. If the script is interrupted, simply run it again to pick up exactly where it left off.
*   **Media Support**: Downloads PDFs, ZIPs, as well as media files like `.wav`, `.mp3`, and `.mp4`.
*   **Collision Handling**: Automatically renames duplicate filenames (e.g. `file_1.pdf`) so no data is overwritten or lost.

### Usage

1.  **Install Dependencies**
    ```bash
    pip install playwright playwright-stealth pymupdf
    playwright install chromium
    ```

2.  **Run Scraper**
    ```bash
    python scrape_epstein.py
    ```

    The script will:
    *   Create an `epstein_files/` directory.
    *   Crawl the Justice.gov pages.
    *   Populate `inventory.json`.
    *   Download all new files.

3.  **Classify Files** (Optional but Recommended)
    ```bash
    python classify_files.py
    ```
    This script analyzes downloaded PDFs to determine if they are **Text** (searchable) or **Scanned** (images). It updates `inventory.json` with this classification, enabling targeted OCR processing.

4.  **Extract Content**
    ```bash
    python extract_content.py
    ```
    Extracts embedded images and text from the PDFs into dedicated subdirectories (e.g., `epstein_files/001/images/`).

5.  **Image Analysis**
    ```bash
    python analyze_images.py [--overwrite]
    ```
    Uses a local LLM to analyze extracted images and generate structured JSON descriptions (`type`, `objects`, `ocr_needed`, etc.).
    
    **Requirements:**
    *   **LM Studio** running on `http://localhost:1234`.
    *   Vision-capable model loaded (e.g., `mistralai/ministral-3-3b` or `llava`).



### Output Structure
The `epstein_files/` directory is organized by document ID. After running all steps, a typical directory looks like:

```text
epstein_files/
├── 001/
│   ├── 001.pdf             # Original file
│   ├── content.txt         # Extracted text content
│   └── images/
│       ├── page1_img1.jpg  # Extracted image
│       └── page1_img1.json # AI Analysis (Type, Description, Objects)
├── 002/
...
```

*   **`inventory.json`**: The source of truth database tracking every file's URL, download status, classification, and analysis progress.
