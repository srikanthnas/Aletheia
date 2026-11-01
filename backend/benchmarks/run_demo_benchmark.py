"""
run_demo_benchmark.py

A standalone script to evaluate the Aletheia pipeline against the demo_assets dataset.
Evaluates each AI source separately against the 'real' baseline.
"""
import sys
import json
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks import BenchmarkRunner, DirectoryDataset
from app.services.ai_forensics.detection_engine import DetectionEngine

class EnsembleAdapter:
    """Wraps DetectionEngine to behave like a single detector for the BenchmarkRunner."""
    def __init__(self):
        self.name = "ensemble"
        self._engine = DetectionEngine.default()
        
    def analyze(self, image):
        res = self._engine.run(image)
        # Duck-type the expected DetectionResult interface (score, confidence)
        return type("MockResult", (), {"score": res.ai_probability, "confidence": res.confidence})

def main():
    base_dir = Path(__file__).resolve().parent.parent.parent / "demo_assets"
    real_dir = base_dir / "real"
    ai_base_dir = base_dir / "ai"
    
    if not real_dir.exists():
        print(f"Error: {real_dir} does not exist. Please run demo_assets/download_samples.py first.")
        return
        
    sources = ["gemini", "dall_e", "midjourney", "stable_diffusion_xl", "flux"]
    
    # Load default individual detectors and append the ensemble
    detectors = BenchmarkRunner._load_default_detectors()
    detectors.append(EnsembleAdapter())
    
    runner = BenchmarkRunner()
    
    master_results = {}
    master_markdown = ["# Aletheia Demo Benchmark Results\n"]
    
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    
    for source in sources:
        fake_dir = ai_base_dir / source
        
        # Check if dir exists and has images
        if not fake_dir.exists():
            print(f"\n[*] Skipping {source} — directory not found.")
            continue
            
        valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
        image_count = sum(1 for p in fake_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_exts)
        
        if image_count == 0:
            print(f"\n[*] Skipping {source} — no images found in {fake_dir}. (Requires manual generation)")
            continue
            
        print(f"\n{'='*60}\nEvaluating Source: {source.upper()}\n{'='*60}")
        
        # We don't want to over-sample real images if fake images are fewer.
        # DirectoryDataset balances classes if max_samples is provided.
        # We want to use all available fake images, so max_samples = image_count * 2
        dataset = DirectoryDataset(real_dir=real_dir, fake_dir=fake_dir, max_samples=image_count * 2)
        
        # Override dataset name for cleaner reports
        dataset_name = f"Demo Dataset ({source.upper()})"
        
        report = runner.run(dataset, detectors=detectors)
        report.dataset_name = dataset_name # Patch name
        
        # Console output
        report.print_summary()
        
        # Save JSON for this specific source
        report.save_json(out_dir / f"benchmark_{source}.json")
        
        # Collect for master report
        master_results[source] = report.to_dict()
        master_markdown.append(report.to_markdown())
        master_markdown.append("\n---\n")
        
    # Save master Markdown
    md_path = out_dir / "master_benchmark.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(master_markdown))
    print(f"\n[+] Master Markdown report saved to {md_path}")
    
    # Save master JSON
    json_path = out_dir / "master_benchmark.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(master_results, f, indent=2)
    print(f"[+] Master JSON report saved to {json_path}")

if __name__ == "__main__":
    main()
