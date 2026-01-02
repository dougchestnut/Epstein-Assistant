# Epstein Assist

A set of tools to scrape, inventory, and analyze files related to the Jeffrey Epstein case released by the Department of Justice.

## Scraper

The project includes a robust scraping script `scrape_epstein.py` designed to fetch all documents and media files from [https://www.justice.gov/epstein](https://www.justice.gov/epstein).

### Features
*   **Comprehensive Crawl**: Recursively finds files in subsections like Court Records and FOIA (FBI, BOP).
*   **Bot Protection Bypass**: Uses `playwright-stealth` and user-like behavior to navigate Akamai protections.
*   **Resumable**: Maintains a local `epstein_files/inventory.json` database. If the script is interrupted, simply run it again to pick up exactly where it left off.
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
    *   Populate `epstein_files/inventory.json`.
    *   Download all new files.

3.  **Classify Files** (Optional but Recommended)
    ```bash
    python classify_files.py
    ```
    This script analyzes downloaded PDFs to determine if they are **Text** (searchable) or **Scanned** (images). It updates `epstein_files/inventory.json` with this classification, enabling targeted OCR processing.

4.  **Extract Content**
    ```bash
    python extract_content.py
    ```
    Extracts embedded images and text from the PDFs into dedicated subdirectories (e.g., `epstein_files/001/images/`).

5.  **Process Images**
    ```bash
    python process_images.py [--overwrite] [--just documents|extracted]
    ```
    Generates web-optimized AVIF derivatives for all images and PDFs found in the inventory.
    *   **Documents (PDFs)**: Generates a lightweight preview (`medium.avif` at 800px, Page 1 only) and an `info.json` with metadata.
    *   **Extracted Images**: Generates sized derivatives (tiny, thumb, small, medium, full).
    *   **Flags**:
        *   `--overwrite`: Force regeneration of existing files (useful for applying new quality settings).
        *   `--just`: Limit scope to `documents` (PDFs only) or `extracted` (Images only).

6.  **Extract Metadata**
    ```bash
    python extract_metadata.py
    ```
    Extracts embedded EXIF and XMP metadata from all images and PDFs in the inventory.
    *   **Output**: Creates a `meta.json` file in the image's or document's directory containing the raw metadata.
    *   **PDF Support**: Extracts XMP, Standard Info, Layers (OCGs), Fonts, Embedded Files, and Annotation summaries.

7.  **Image Analysis**
    ```bash
    python analyze_images.py [--overwrite]
    ```
    Uses a local LLM to analyze extracted images and generate structured JSON descriptions (`type`, `objects`, `ocr_needed`, etc.).
    
    **Requirements:**
    *   Vision-capable model loaded (e.g., `mistralai/ministral-3-3b` or `llava`).

8.  **Perform OCR**
    ```bash
    python perform_ocr.py [--dry-run]
    ```
    Walks through the `epstein_files` directory and performs OCR on images flagged with `"needs_ocr": true` in their `analysis.json` file.
    
    **Features:**
    *   **Smart Selection**: Prioritizes original high-quality images (`.png`/`.jpg`) over compressed `.avif` if available.
    *   **Auto-Resize**: Automatically resizes images larger than 2048px to prevent API errors.
    *   **Resumable**: Skips directories where `ocr.txt` already exists.
    *   **Dry Run**: Use `--dry-run` to see what files would be processed without making API calls.
    
    **Requirements:**
    *   **LM Studio** running on `http://localhost:1234` (or configured URL).
    *   An OCR-capable model loaded (recommended: `allenai/olmocr-2-7b`).

9.  **Perform PDF OCR**
    ```bash
    python perform_pdf_ocr.py [--dry-run] [--overwrite]
    ```
    Performs page-by-page OCR on the full PDF documents using LM Studio. This is useful for documents that are scanned images without embedded text.
    *   **Features**:
        *   Renders each page to a high-quality PNG (1288px max dimension).
        *   Sends page + expert prompt to LM Studio.
        *   Aggregates pages into a single `ocr.md` markdown file.
    *   **Requirements**: Same as Image OCR (LM Studio + Vision Model).

10. **Transcribe Media**
    ```bash
    python transcribe_media.py [--model large-v2] [--device cpu|cuda]
    ```
    Transcribes audio/video files (mp3, wav, mp4, etc.) found in the inventory using WhisperX. It generates a `.vtt` subtitle file next to the media file.

    **Requirements:**
    *   **FFmpeg** must be installed and on your system PATH.
    *   **WhisperX**:
        ```bash
        pip install git+https://github.com/m-bain/whisperX.git
        ```
    *   **HuggingFace Token** (Optional): Set `HF_TOKEN` in `.env` for speaker diarization (requires accepting pyannote terms).



11. **Detect Faces**
    ```bash
    python detect_faces.py [--overwrite]
    ```
    Scans all images in the inventory for faces using `insightface`.
    *   **Features:**
        *   Detects bounding boxes, landmarks, and extracts embeddings for facial recognition/clustering.
        *   Saves results to `faces.json` in the image's directory.
        *   Ignores `has_faces` flag from analysis (processes everything) for maximum coverage.
    *   **Requirements:**
        *   `insightface` and `onnxruntime` installed (included in requirements.txt).

### Output Structure
The `epstein_files/` directory is organized by document ID. After running all steps, a typical directory looks like:

```text
epstein_files/
├── 001/
│   ├── 001.pdf                  # Original file
│   ├── content.txt              # Extracted text content
│   └── images/
│       ├── page1_img1.jpg       # Original extracted image
│       └── page1_img1/          # Analysis & Formats Directory
│           ├── analysis.json    # AI Analysis (Type, Description, Objects)
│           ├── meta.json        # EXIF/XMP Metadata
│           ├── ocr.txt          # OCR text (if text was detected)
│           ├── full.avif        # Web-optimized full resolution
│           ├── medium.avif      # Medium sized thumbnail
│           ├── small.avif       # Small sized thumbnail
│           ├── thumb.avif       # Thumbnail
│           └── tiny.avif        # Tiny placeholder
├── 002/
...
```

*   **`epstein_files/inventory.json`**: The source of truth database tracking every file's URL, download status, classification, and analysis progress.
