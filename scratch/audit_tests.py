import io
import time
import requests
import pymongo
from PIL import Image, ImageEnhance
from io import BytesIO
import random

BASE_URL = "http://localhost:8000/api"
MONGO_URL = "mongodb://localhost:27017" # assuming default

print("Starting Automated Audit...")

def create_test_image(size=(400, 400), color=(100, 150, 200)):
    img = Image.new("RGB", size, color)
    # Add some noise to make pHash non-trivial and realistic
    pixels = img.load()
    for i in range(size[0]):
        for j in range(size[1]):
            pixels[i,j] = (color[0] + random.randint(-20, 20), color[1] + random.randint(-20, 20), color[2] + random.randint(-20, 20))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr

def run_tests():
    try:
        db_client = pymongo.MongoClient(MONGO_URL)
        db = db_client["aletheia"] # check if it's correct db name, in connection.py it's settings.DATABASE_NAME -> wait let me check connection.py
        # Fallback to motor to fetch db name? The backend is running.
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")

    # 1. Registration
    print("\n--- PHASE 2: Registration ---")
    start_time = time.time()
    img_bytes = create_test_image()
    res = requests.post(f"{BASE_URL}/register", files={"file": ("test.png", img_bytes, "image/png")}, data={"model_name": "Flux"})
    reg_time = time.time() - start_time
    print(f"Register Status: {res.status_code}, Time: {reg_time:.4f}s")
    if res.status_code != 200:
        print("Registration failed:", res.text)
        return
    reg_data = res.json()
    image_id = reg_data["metadata"]["image_id"]
    print("Registered image_id:", image_id)

    # 2. Embedding
    print("\n--- PHASE 3: Embedding ---")
    start_time = time.time()
    res = requests.post(f"{BASE_URL}/embed", json={"image_id": image_id})
    emb_time = time.time() - start_time
    print(f"Embed Status: {res.status_code}, Time: {emb_time:.4f}s")
    emb_data = res.json()
    download_url = emb_data["embedded_image"]

    # Download embedded image
    res = requests.get(f"http://localhost:8000{download_url}")
    emb_img_bytes = res.content
    print("Downloaded embedded image size:", len(emb_img_bytes))

    # 3. Extraction
    print("\n--- PHASE 4: Extraction ---")
    start_time = time.time()
    res = requests.post(f"{BASE_URL}/extract", files={"file": ("emb.png", emb_img_bytes, "image/png")})
    ext_time = time.time() - start_time
    print(f"Extract Status: {res.status_code}, Time: {ext_time:.4f}s")
    print("Extract MIR:", res.json()["mir"]["media_id"] if res.status_code==200 else res.text)

    # 4. Verification on Original
    print("\n--- PHASE 5: Verification (Original) ---")
    start_time = time.time()
    res = requests.post(f"{BASE_URL}/verify", files={"file": ("emb.png", emb_img_bytes, "image/png")})
    ver_time = time.time() - start_time
    print(f"Verify Status: {res.status_code}, Time: {ver_time:.4f}s")
    if res.status_code == 200:
        v_data = res.json()
        print(f"Verdict: {v_data['verification']}, Similarity: {v_data['similarity']}%")
    else:
        print("Verification failed:", res.text)

    # Verification on JPEG conversion
    print("\n--- PHASE 5: Verification (JPEG converted) ---")
    img = Image.open(io.BytesIO(emb_img_bytes))
    jpeg_io = io.BytesIO()
    img.convert('RGB').save(jpeg_io, format='JPEG', quality=90)
    jpeg_io.seek(0)
    res = requests.post(f"{BASE_URL}/verify", files={"file": ("test.jpg", jpeg_io, "image/jpeg")})
    print(f"Verify JPEG Status: {res.status_code}, Msg: {res.text[:100]}")

    # Verification on Cropped Image
    print("\n--- PHASE 5: Verification (Cropped) ---")
    cropped = img.crop((50, 50, 350, 350))
    crop_io = io.BytesIO()
    cropped.save(crop_io, format='PNG')
    crop_io.seek(0)
    res = requests.post(f"{BASE_URL}/verify", files={"file": ("test.png", crop_io, "image/png")})
    print(f"Verify Crop Status: {res.status_code}, Msg: {res.text[:100]}")
    
    # Verification on Brightness changed
    print("\n--- PHASE 5: Verification (Brightness Adjusted) ---")
    enhancer = ImageEnhance.Brightness(img)
    bright = enhancer.enhance(1.2)
    bright_io = io.BytesIO()
    bright.save(bright_io, format='PNG')
    bright_io.seek(0)
    res = requests.post(f"{BASE_URL}/verify", files={"file": ("test.png", bright_io, "image/png")})
    print(f"Verify Brightness Status: {res.status_code}")
    if res.status_code == 200:
        v_data = res.json()
        print(f"Verdict: {v_data['verification']}, Similarity: {v_data['similarity']}%")
    else:
        print("Error:", res.text[:100])

    # Security: empty payload, invalid format, too large
    print("\n--- PHASE 10: Security ---")
    res = requests.post(f"{BASE_URL}/register", files={"file": ("test.txt", b"hello world", "text/plain")}, data={"model_name": "Flux"})
    print("Register Text File Status:", res.status_code)
    
    # Check DB
    print("\n--- PHASE 6: Database ---")
    try:
        db_client = pymongo.MongoClient(MONGO_URL)
        db = db_client["aletheia"] # Check if database is named aletheia
        doc = db["registered_media"].find_one({"image_id": image_id})
        if doc:
            print("DB Document found.")
            fields = ["image_id", "model_name", "timestamp", "mir", "embedding_strategy", "phash", "embedded_image_path"]
            for f in fields:
                print(f"Contains {f}: {f in doc}")
    except Exception as e:
        print("DB check failed:", e)

if __name__ == "__main__":
    run_tests()
