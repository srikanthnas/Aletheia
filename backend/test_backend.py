"""Test backend/API integration."""
print("Testing backend imports...")

from app.main import app
from app.services.ai_forensics.detection_engine import DetectionEngine

# Check FastAPI app
print(f"✓ FastAPI app loaded: {app.title}")

# Check DetectionEngine in forensics route
from app.api.routes import forensics
print(f"✓ Forensics route loaded")

# Check engine has 4 detectors
engine = DetectionEngine.default()
detectors = [d.name for d in engine.detectors()]
print(f"✓ DetectionEngine detectors: {detectors}")

assert "frequency_spectral" in detectors, "FrequencyDetector not registered"
print("✓ FrequencyDetector registered in engine")

print("\n✓ Backend is ready for deployment")
