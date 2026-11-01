"""
benchmark.py - Comprehensive evaluation of LSB vs DCT Strategies
"""
import asyncio
import io
import time
import uuid
import random
from datetime import datetime, timezone
import pandas as pd
from PIL import Image, ImageEnhance
import numpy as np
import warnings

# Suppress expected warnings from pandas or PIL if any
warnings.filterwarnings("ignore")

# Aletheia Imports
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.embedding.binary_encoder import encode
from app.services.extraction.adpe_strategy import ADPEStrategy
from app.services.dct.dct_strategy import DCTStrategy
from app.services.provenance_extraction_service import extract_provenance
from app.services.verification.verification_service import verify_provenance
from app.utils.metrics import calculate_psnr, calculate_mse, calculate_ssim
from app.services.verification.phash_service import generate_phash

def create_test_image(size=(512, 512)):
    color = (random.randint(50,200), random.randint(50,200), random.randint(50,200))
    img = Image.new("RGB", size, color)
    pixels = img.load()
    for i in range(size[0]):
        for j in range(size[1]):
            pixels[i,j] = (
                min(255, max(0, color[0] + random.randint(-30, 30))),
                min(255, max(0, color[1] + random.randint(-30, 30))),
                min(255, max(0, color[2] + random.randint(-30, 30)))
            )
    return img

class DummyDB:
    def __init__(self, expected_phash, strategy_name):
        self.expected_phash = expected_phash
        self.strategy_name = strategy_name
    def __getitem__(self, key):
        class DummyColl:
            def __init__(self, parent): self.parent = parent
            async def find_one(self, *args, **kwargs):
                return {'phash': self.parent.expected_phash, 'embedding_strategy': self.parent.strategy_name}
        return DummyColl(self)

async def run_benchmark():
    media_id = str(uuid.uuid4())
    mir = build_mir(media_id=media_id, model_name="Benchmark", timestamp=datetime.now(timezone.utc).isoformat())
    payload = serialize(mir)
    bitstream = encode(payload)
    
    strategies = [
        ("LSB-ADPE", ADPEStrategy()),
        ("DCT-QIM", DCTStrategy())
    ]

    base_img = create_test_image((512, 512))
    
    print("\n=====================================")
    print("1. Functional Verification & Quality")
    print("=====================================")
    
    quality_rows = []
    performance_rows = []
    
    emb_images = {}
    db_mocks = {}
    
    for name, strategy in strategies:
        # Performance: Embedding
        emb_times = []
        for _ in range(10):
            start = time.perf_counter()
            _ = strategy.embed(base_img.copy(), bitstream)
            emb_times.append(time.perf_counter() - start)
            
        avg_emb_time = np.mean(emb_times) * 1000 # ms
        
        # Get one embedded image for the rest of tests
        emb_img = strategy.embed(base_img.copy(), bitstream)
        emb_images[name] = emb_img
        
        # Store phash for verification logic
        phash_val = generate_phash(emb_img)
        db = DummyDB(expected_phash=phash_val, strategy_name=name)
        db_mocks[name] = db
        
        # Quality Metrics
        psnr = calculate_psnr(base_img, emb_img)
        mse = calculate_mse(base_img, emb_img)
        ssim = calculate_ssim(base_img, emb_img)
        quality_rows.append({"Strategy": name, "PSNR (dB)": psnr, "MSE": mse, "SSIM": ssim})
        
        # Performance: Extraction & Verification
        ext_times = []
        for _ in range(10):
            start = time.perf_counter()
            await extract_provenance(emb_img.copy(), db)
            ext_times.append(time.perf_counter() - start)
        avg_ext_time = np.mean(ext_times) * 1000
        
        ver_times = []
        for _ in range(10):
            start = time.perf_counter()
            await verify_provenance(emb_img.copy(), db)
            ver_times.append(time.perf_counter() - start)
        avg_ver_time = np.mean(ver_times) * 1000
        
        performance_rows.append({
            "Strategy": name,
            "Embedding (ms)": avg_emb_time,
            "Extraction (ms)": avg_ext_time,
            "Verification (ms)": avg_ver_time
        })
        
    print("\n--- Image Quality ---")
    print(pd.DataFrame(quality_rows).to_markdown(index=False))
    
    print("\n--- Performance (Avg over 10 runs) ---")
    print(pd.DataFrame(performance_rows).to_markdown(index=False))

    print("\n=====================================")
    print("2. Robustness Testing")
    print("=====================================")
    
    distortions = [
        ("PNG Save", lambda img: save_load(img, "PNG")),
        ("JPEG 95%", lambda img: save_load(img, "JPEG", quality=95)),
        ("JPEG 90%", lambda img: save_load(img, "JPEG", quality=90)),
        ("JPEG 80%", lambda img: save_load(img, "JPEG", quality=80)),
        ("JPEG 70%", lambda img: save_load(img, "JPEG", quality=70)),
        ("Brightness +10%", lambda img: ImageEnhance.Brightness(img).enhance(1.1)),
        ("Brightness +20%", lambda img: ImageEnhance.Brightness(img).enhance(1.2)),
        ("Contrast +10%", lambda img: ImageEnhance.Contrast(img).enhance(1.1)),
        ("Resize 95%", lambda img: img.resize((int(img.width * 0.95), int(img.height * 0.95)))),
        ("Resize 80%", lambda img: img.resize((int(img.width * 0.8), int(img.height * 0.8)))),
        ("Crop 5%", lambda img: img.crop((int(img.width*0.025), int(img.height*0.025), int(img.width*0.975), int(img.height*0.975)))),
        ("Crop 10%", lambda img: img.crop((int(img.width*0.05), int(img.height*0.05), int(img.width*0.95), int(img.height*0.95)))),
        ("Gaussian Noise", lambda img: add_gaussian_noise(img))
    ]
    
    robustness_rows = []
    
    for name, _ in strategies:
        emb_img = emb_images[name]
        db = db_mocks[name]
        
        for dist_name, dist_func in distortions:
            dist_img = dist_func(emb_img.copy())
            
            try:
                res = await verify_provenance(dist_img, db)
                status = res.status
                recovered_regions = getattr(res, 'recovered_regions', 1)
                total_regions = getattr(res, 'total_regions', 1)
                if total_regions == 0: total_regions = 1
                rec_perc = (recovered_regions / total_regions) * 100
                sim = res.similarity
                ham = res.hamming_distance
                mir_rec = "Yes"
            except Exception as e:
                status = "FAILED"
                mir_rec = "No"
                rec_perc = 0
                sim = "-"
                ham = "-"
                
            robustness_rows.append({
                "Strategy": name,
                "Distortion": dist_name,
                "MIR Recovery": mir_rec,
                "Rec. %": rec_perc,
                "Verdict": status,
                "Sim (%)": sim,
                "Hamming": ham
            })
            
    df_robust = pd.DataFrame(robustness_rows)
    print(df_robust.to_markdown(index=False))
    
    with open("benchmark_robustness.md", "w") as f:
        f.write(df_robust.to_markdown(index=False))

    print("\n=====================================")
    print("3. Capacity")
    print("=====================================")
    
    sizes = [(256, 256), (512, 512), (1024, 1024)]
    capacity_rows = []
    
    for size in sizes:
        test_img = create_test_image(size)
        for name, strategy in strategies:
            cap = strategy.capacity(test_img)
            capacity_rows.append({
                "Strategy": name,
                "Resolution": f"{size[0]}x{size[1]}",
                "Capacity (bits)": cap,
                "Capacity (bytes)": cap // 8
            })
            
    print(pd.DataFrame(capacity_rows).to_markdown(index=False))

def save_load(img, format, **kwargs):
    buf = io.BytesIO()
    img.save(buf, format=format, **kwargs)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
    
def add_gaussian_noise(img):
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, 5, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
