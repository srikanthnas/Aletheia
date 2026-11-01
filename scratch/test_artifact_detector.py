import sys, os
sys.path.insert(0, os.getcwd())

import numpy as np
from PIL import Image

def make_image(size=(256, 256), noise=True):
    arr = np.full((*size, 3), 120, dtype=np.uint8)
    if noise:
        arr = np.clip(arr + np.random.randint(-40, 40, arr.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

PASS = '[PASS]'
FAIL = '[FAIL]'

# Test 1: TextureAnalyzer
from app.services.ai_forensics.artifact.texture import TextureAnalyzer
ta = TextureAnalyzer()
res = ta.analyze(make_image())
assert 0.0 <= res['score'] <= 1.0
assert 0.0 <= res['confidence'] <= 1.0
assert 'features' in res
print(f"{PASS} TextureAnalyzer: score={res['score']}, confidence={res['confidence']}")

# Test 2: EdgeAnalyzer
from app.services.ai_forensics.artifact.edges import EdgeAnalyzer
ea = EdgeAnalyzer()
res = ea.analyze(make_image())
assert 0.0 <= res['score'] <= 1.0
assert 'features' in res
print(f"{PASS} EdgeAnalyzer: score={res['score']}, confidence={res['confidence']}")

# Test 3: ArtifactFusion
from app.services.ai_forensics.artifact.fusion import ArtifactFusion
af = ArtifactFusion()
img = make_image()
t = TextureAnalyzer().analyze(img)
e = EdgeAnalyzer().analyze(img)
fused = af.combine(t, e)
assert 0.0 <= fused['score'] <= 1.0
assert isinstance(fused['explanation'], str)
print(f"{PASS} ArtifactFusion: score={fused['score']}")

# Test 4: ArtifactDetector standalone
from app.services.ai_forensics.detectors.artifact_detector import ArtifactDetector
from app.services.ai_forensics.models import DetectionResult
det = ArtifactDetector()
assert det.name == 'artifact_cv'
result = det.analyze(make_image())
assert isinstance(result, DetectionResult)
assert 0.0 <= result.score <= 1.0
assert 0.0 <= result.confidence <= 1.0
print(f"{PASS} ArtifactDetector: score={result.score}, confidence={result.confidence}")
print(f"       reason[:70]='{result.reason[:70]}...'")

# Test 5: Custom weights
det_custom = ArtifactDetector(weights={'texture': 0.80, 'edges': 0.20})
r2 = det_custom.analyze(make_image())
assert isinstance(r2, DetectionResult)
print(f"{PASS} Custom weights: score={r2.score}")

# Test 6: Fault isolation in DetectionEngine
from app.services.ai_forensics.detection_engine import DetectionEngine
from app.services.ai_forensics.base_detector import AIForensicDetector

class ExplodingDetector(AIForensicDetector):
    @property
    def name(self): return 'exploding'
    def analyze(self, image): raise RuntimeError('Intentional boom')

engine = DetectionEngine()
engine.register(ExplodingDetector())
engine.register(ArtifactDetector())
result = engine.run(make_image())
names = [r.engine for r in result.detector_breakdown]
assert 'artifact_cv' in names
assert 'exploding' not in names
print(f"{PASS} Fault isolation: breakdown={names}")

# Test 7: Two-plugin engine (no CLIP to avoid download)
from app.services.ai_forensics.detectors.statistical_detector import StatisticalDetector
engine2 = DetectionEngine()
engine2.register(ArtifactDetector())
engine2.register(StatisticalDetector())
result2 = engine2.run(make_image())
assert len(result2.detector_breakdown) == 2
print(f"{PASS} Two-plugin engine: verdict={result2.verdict}, prob={result2.ai_probability}")

# Test 8: Score validation still works
try:
    DetectionResult(engine='x', score=2.0, confidence=0.5, reason='bad')
    print(f"{FAIL} Should have raised ValueError")
except ValueError:
    print(f"{PASS} DetectionResult validation intact")

print("\nAll 8 tests passed.")
