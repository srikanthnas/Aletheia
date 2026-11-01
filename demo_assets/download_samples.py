"""
download_samples.py

A helper script to automatically download openly available, permissively licensed
images for the Aletheia demonstration dataset.

- Real images: Sourced from Lorem Picsum (Unsplash license / CC0).
- AI images: Sourced via the Wikimedia Commons API from specific AI-generator categories (CC0/Public Domain).

Requirements:
- Python 3
- urllib (standard library)
"""

import os
import json
import urllib.request
import urllib.parse
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
REAL_DIR = BASE_DIR / "real"
AI_DIR = BASE_DIR / "ai"

# How many images to download per category
SAMPLES_PER_CATEGORY = 5

def download_image(url: str, dest_path: Path):
    """Download an image from a URL to the specified destination."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'AletheiaDemoBot/1.0 (https://github.com/yourusername/aletheia; your@email.com)'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        print(f"  [+] Downloaded: {dest_path.name}")
        return True
    except Exception as e:
        print(f"  [-] Failed to download {url}: {e}")
        return False

def get_wikimedia_commons_images(category: str, limit: int = 5) -> list[str]:
    """Fetch image URLs from a specific Wikimedia Commons category."""
    # API endpoint for Wikimedia Commons
    api_url = "https://commons.wikimedia.org/w/api.php"
    
    # Parameters to get files in a category
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": limit * 2, # Fetch extra in case some aren't images
    }
    
    query_string = urllib.parse.urlencode(params)
    request_url = f"{api_url}?{query_string}"
    
    image_urls = []
    
    try:
        req = urllib.request.Request(
            request_url,
            headers={'User-Agent': 'AletheiaDemoBot/1.0'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            members = data.get("query", {}).get("categorymembers", [])
            for member in members:
                title = member.get("title", "")
                if title.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    # To get the actual file URL, we need another API call or use the special File path
                    # A neat trick to get the image URL directly without a second API call:
                    # https://commons.wikimedia.org/wiki/Special:FilePath/File_name.ext
                    file_name = title.replace("File:", "").replace(" ", "_")
                    direct_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(file_name)}?width=512"
                    image_urls.append(direct_url)
                    
                    if len(image_urls) >= limit:
                        break
    except Exception as e:
        print(f"  [-] Error querying Wikimedia Commons API for {category}: {e}")
        
    return image_urls

def download_real_images(count: int):
    """Download placeholder 'real' photographs from Lorem Picsum."""
    print("\nDownloading 'Real' images (Lorem Picsum)...")
    os.makedirs(REAL_DIR, exist_ok=True)
    
    for i in range(1, count + 1):
        # Using a seed ensures we get the same image every time for reproducibility
        url = f"https://picsum.photos/seed/aletheia_real_{i}/512/512.jpg"
        dest = REAL_DIR / f"real_sample_{i}.jpg"
        if not dest.exists():
            download_image(url, dest)
        else:
            print(f"  [*] Skipping {dest.name} (already exists)")

def download_ai_images():
    """Download AI generated images from Wikimedia Commons and official repos."""
    print("\nDownloading AI-generated images...")
    
    # Mapping of local directories to Wikimedia Commons categories
    categories = {
        "midjourney": "Images_generated_by_Midjourney",
        "dall_e": "Images_generated_by_DALL-E_3",
        "stable_diffusion_xl": "Images_generated_by_Stable_Diffusion_XL",
        "flux": "Images_generated_by_FLUX.1", 
        "gemini": "Images_generated_by_Google_Gemini"
    }
    
    # Hardcoded direct URLs from official documentation or datasets (Hugging Face)
    direct_fallback_urls = {
        "stable_diffusion_xl": [
            "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/sdxl-text2img.png",
            "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/sdxl-img2img.png",
            "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/sdxl-inpaint.png",
        ],
        "flux": [
            "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/flux-dev.png",
            "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/flux-schnell.png",
        ]
    }
    
    for local_dir, category in categories.items():
        print(f"\nFetching {local_dir} samples...")
        target_dir = AI_DIR / local_dir
        os.makedirs(target_dir, exist_ok=True)
        
        urls = get_wikimedia_commons_images(category, SAMPLES_PER_CATEGORY)
        
        if not urls:
            if local_dir in direct_fallback_urls:
                print(f"  [!] No images found on Wikimedia Commons for {local_dir}.")
                print(f"  [*] Attempting to fetch from official Hugging Face sample repositories...")
                urls = direct_fallback_urls[local_dir]
            else:
                print(f"  [!] WARNING: No public images found for {local_dir} and no fallback repository available.")
                print(f"  [!] MANUAL ACTION REQUIRED: Please generate and add sample images to 'demo_assets/ai/{local_dir}' manually.")
                continue
            
        success_count = 0
        for i, url in enumerate(urls, 1):
            dest = target_dir / f"{local_dir}_sample_{i}.jpg"
            if not dest.exists():
                if download_image(url, dest):
                    success_count += 1
            else:
                print(f"  [*] Skipping {dest.name} (already exists)")
                success_count += 1
                
        if success_count == 0:
            print(f"  [!] WARNING: All download attempts failed for {local_dir}.")
            print(f"  [!] MANUAL ACTION REQUIRED: Please generate and add sample images to 'demo_assets/ai/{local_dir}' manually.")

def main():
    print("Aletheia Demo Dataset Downloader")
    print("================================")
    print("This script downloads openly available images for demonstration purposes.")
    
    download_real_images(SAMPLES_PER_CATEGORY)
    download_ai_images()
    
    print("\nDownload complete!")
    print(f"Check the '{BASE_DIR.name}' directory for the downloaded files.")

if __name__ == "__main__":
    main()
