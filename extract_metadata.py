import os
import json
import warnings
from PIL import Image, ExifTags
import fitz  # PyMuPDF

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

def extract_pdf_metadata(pdf_path):
    meta = {}
    try:
        doc = fitz.open(pdf_path)
        
        # 1. Standard Metadata
        meta['info'] = doc.metadata
        
        # 2. XMP Metadata
        xmp = doc.get_xml_metadata()
        if xmp:
            meta['xmp'] = xmp
            
        # 3. Layers (OCGs - Optional Content Groups)
        # PyMuPDF exposes this via layer_ui_configs if simple, or get_ocgs() for low level
        try:
            layers = doc.layer_ui_configs()
            if layers:
                meta['layers'] = [layer['text'] for layer in layers if 'text' in layer]
        except:
            pass

        # 4. Embedded Files
        try:
            embedded = []
            for count, name in enumerate(doc.embedded_files):
                # Retrieve info about the embedded file
                # name is the key for get_embedded_file(name)
                # but we just want the list for now
                embedded.append(name)
            if embedded:
                meta['embedded_files'] = embedded
        except:
            pass
            
        # 5. Fonts (Sample from first few pages to avoid massive overhead)
        fonts = set()
        try:
            for i in range(min(3, doc.page_count)):
                page = doc[i]
                for font in page.get_fonts():
                    # (xref, ext, type, basefont, name, encoding)
                    if len(font) > 3:
                        fonts.add(font[3])
            if fonts:
                meta['fonts'] = list(fonts)
        except:
            pass

        # 6. Annotations (Summary)
        annot_count = 0
        annot_types = set()
        try:
            for page in doc:
                for annot in page.annots():
                    annot_count += 1
                    annot_types.add(annot.type[1]) # type is typically (int, description)
        except:
            pass
            
        if annot_count > 0:
            meta['annotations'] = {
                "count": annot_count,
                "types": list(annot_types)
            }
            
        meta['page_count'] = doc.page_count
        meta['is_encrypted'] = doc.is_encrypted
        
        doc.close()
    except Exception as e:
        meta['error'] = str(e)
        
    return meta

def main():
    abs_target_dir = os.path.abspath(TARGET_DIR)
    
    print(f"Scanning {abs_target_dir} for images and PDFs...")
    
    count = 0
    saved_count = 0
    
    for root, dirs, files in os.walk(abs_target_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)
            file_stem = os.path.splitext(file)[0]
            
            # --- IMAGE PROCESSING ---
            if ext in IMAGE_EXTENSIONS:
                try:
                    with Image.open(file_path) as img:
                        exif = extract_exif(img)
                        xmp = extract_xmp(img)
                        
                        if exif or xmp:
                            target_dir = os.path.join(root, file_stem)
                            os.makedirs(target_dir, exist_ok=True)
                            
                            meta_file_path = os.path.join(target_dir, "meta.json")
                            metadata = {"exif": exif, "xmp": xmp}
                            
                            with open(meta_file_path, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2)
                            saved_count += 1
                except Exception as e:
                    # pass
                    pass
                count += 1

            # --- PDF PROCESSING ---
            elif ext == ".pdf":
                # Determine target directory for PDF metadata
                # Rule: If pdf is '021.pdf', check Key Directory '021'
                target_dir = None
                
                # Case 1: PDF is inside the document directory (e.g. 021/021.pdf) -> use root
                if file_stem == os.path.basename(root):
                    target_dir = root
                
                # Case 2: PDF is sibling (e.g. 021.pdf next to 021/) -> use sibling dir
                else:
                    sibling_dir = os.path.join(root, file_stem)
                    if os.path.isdir(sibling_dir):
                        target_dir = sibling_dir
                
                if target_dir:
                    metadata = extract_pdf_metadata(file_path)
                    if metadata:
                        meta_file_path = os.path.join(target_dir, "meta.json")
                        
                        # Merge with existing if present (e.g. if we had other tools write to it)
                        if os.path.exists(meta_file_path):
                            try:
                                with open(meta_file_path, 'r', encoding='utf-8') as f:
                                    existing = json.load(f)
                                    existing.update(metadata)
                                    metadata = existing
                            except:
                                pass # Overwrite if corrupt
                        
                        with open(meta_file_path, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=2)
                        saved_count += 1
                count += 1

            if count % 1000 == 0:
                print(f"Processed {count} files... (Saved {saved_count} meta files)")

    print(f"Finished. Processed {count} files. Created/Updated {saved_count} meta.json files.")

if __name__ == "__main__":
    main()
