
import os
import json
import argparse
import time
import torch
from pathlib import Path

# Try to import python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not found. Environment variables must be set manually.")

# Try to import whisperx
try:
    import whisperx
except ImportError:
    whisperx = None

INVENTORY_FILE = "inventory.json"
HF_TOKEN = os.getenv("HF_TOKEN")

def load_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return {}
    with open(INVENTORY_FILE, 'r') as f:
        return json.load(f)

def save_inventory(inventory):
    with open(INVENTORY_FILE, 'w') as f:
        json.dump(inventory, f, indent=2)

def seconds_to_vtt_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:06.3f}"

def write_vtt(segments, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for segment in segments:
            start = seconds_to_vtt_timestamp(segment["start"])
            end = seconds_to_vtt_timestamp(segment["end"])
            speaker = segment.get("speaker", "UNKNOWN")
            text = segment["text"].strip()
            f.write(f"{start} --> {end}\n")
            f.write(f"[{speaker}]: {text}\n\n")

def main():
    if whisperx is None:
        print("Error: whisperx module not found. Please install it using:")
        print("pip install git+https://github.com/m-bain/whisperX.git")
        return

    parser = argparse.ArgumentParser(description="Transcribe media files using WhisperX")
    parser.add_argument("--device", type=str, default="cpu", help="Device to use (cpu, cuda, mps)")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for transcription")
    parser.add_argument("--model", type=str, default="large-v2", help="Whisper model to use")
    
    args = parser.parse_args()
    
    # Auto-detect MPS (Apple Silicon) if not explicitly set
    device = args.device
    # if device == "cpu" and torch.backends.mps.is_available():
    #     print("Detected Apple Silicon. Using 'mps' device.")
    #     device = "mps"
        
    compute_type = "float16" if device == "cuda" else "float32" # float16 not supported on mps/cpu usually
    print(f"Using device: {device}, compute_type: {compute_type}")

    if not HF_TOKEN:
        print("Warning: HF_TOKEN not found in environment. Diarization might fail if it requires authentication.")
    
    # Load Inventory
    inventory = load_inventory()
    print(f"Loaded {len(inventory)} items from inventory.")
    
    # Filter for media files not yet transcribed
    media_extensions = ('.mp3', '.wav', '.mp4', '.m4a', '.mov')
    to_process = []
    
    for url, meta in inventory.items():
        local_path = meta.get("local_path")
        if not local_path or not os.path.exists(local_path):
            continue
        
        if local_path.lower().endswith(media_extensions):
            # Check if VTT exists
            vtt_path = os.path.splitext(local_path)[0] + ".vtt"
            if not os.path.exists(vtt_path) or meta.get("transcription_status") != "done":
                to_process.append((url, meta, local_path, vtt_path))
    
    if not to_process:
        print("No new media files to transcribe.")
        return

    print(f"Found {len(to_process)} media files to process.")

    # 1. Load Whisper Model
    print(f"Loading Whisper model {args.model}...")
    try:
        model = whisperx.load_model(args.model, device, compute_type=compute_type)
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    # 2. Load Alignment Model (will do per language later, but usually defaults to En)
    # We'll assume English for now or let whisperx handle it?
    # WhisperX requires loading alignment model separately.
    # We do this inside loop if we assume english? Or assume dominant language.
    # Let's load the english alignment model once for efficiency if possible.
    # Actually, alignment depends on the language detected.
    
    # 3. Load Diarization Pipeline
    print("Loading Diarization pipeline...")
    try:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
    except Exception as e:
        print(f"Failed to load diarization pipeline (check HF_TOKEN): {e}")
        return

    for url, meta, local_path, vtt_path in to_process:
        print(f"Processing {local_path}...")
        try:
            # A. Transcribe
            audio = whisperx.load_audio(local_path)
            result = model.transcribe(audio, batch_size=args.batch_size)
            
            # Detected language
            language = result["language"]
            print(f"Detected language: {language}")
            
            # B. Align
            # load alignment model
            print("Aligning...")
            model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            
            # C. Diarize
            print("Diarizing...")
            diar_segments = diarize_model(audio)
            
            # D. Merge
            result = whisperx.assign_word_speakers(diar_segments, result)
            
            # E. Save VTT
            print(f"Saving VTT to {vtt_path}")
            write_vtt(result["segments"], vtt_path)
            
            meta["transcription_status"] = "done"
            meta["vtt_path"] = vtt_path
            
            # Update inventory immediately
            inventory = load_inventory() # Reload checking for race?
            if url in inventory:
                inventory[url]["transcription_status"] = "done"
                inventory[url]["vtt_path"] = vtt_path
                save_inventory(inventory)
                
        except Exception as e:
            print(f"Error processing {local_path}: {e}")
            # Continue to next file
            continue

if __name__ == "__main__":
    main()
