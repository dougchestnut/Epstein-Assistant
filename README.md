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
    pip install playwright playwright-stealth
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

### Output
*   **`epstein_files/`**: Directory containing all downloaded documents.
*   **`inventory.json`**: Metadata for every file found, including source URL and download status.
