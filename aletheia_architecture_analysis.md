# Aletheia — Architecture Analysis
> Reviewed: 2026-08-03 | Version: 4.0.0

---

## System Overview

Aletheia is a **dual-pipeline** AI media provenance and forensics framework. It operates in two distinct, independent directions:

| Direction | Purpose |
|-----------|---------|
| **Embed / Register** | Stamp AI-generated images with a traceable identity record |
| **Verify / Detect** | Determine whether an image is authentic, AI-generated, tampered, or unregistered |

The system is NOT a simple binary AI detector. It fuses **active provenance signals** (embedded watermarks) with **passive forensic signals** (statistical + spectral + semantic analysis) to produce a holistic trust assessment.

---

## Backend Architecture — Sprint Progression

### Sprint 1 — Media Registration Engine
**Route:** `POST /api/register`  
**Service:** `registration_service.py`  
**DB Model:** `models/media.py` → MongoDB `registered_media` collection  

Registers an AI-generated image: assigns UUID v4, stores metadata (model name, timestamp, media type, framework version).

---

### Sprint 2 — Provenance Embedding Engine
**Route:** `POST /api/embed`  
**Service:** `provenance_embedding_service.py`  
**Pipeline:**
```
MongoDB doc → MIR construction → JSON serialization → Binary bitstream → EmbeddingStrategy.embed() → PNG save → phash store → DB update
```

**Embedding abstraction:**
```
EmbeddingStrategy (ABC)
  ├── LSBStrategy        (Sprint 2 — sequential LSB across full image)
  └── ADPEStrategy       (Sprint 3+5 — region-aware adaptive embedding)
```
Both implement the same `embed(image, bitstream) → Image` interface — fully swappable via DI in `embed_provenance()`.

---

### Sprint 3 — Adaptive Distributed Provenance Embedding (ADPE)
**Default strategy in `provenance_embedding_service.py`:** `ADPEStrategy`  
**Key components:**
- `RegionManager` — partitions image into adaptive grid (1×1 → 8×8) based on resolution
- `PayloadAllocator` — manages bit allocation across regions
- `ADPEStrategy` — embeds full MIR redundantly into all grid regions (Sprint 5 extension already active: `STRATEGY_NAME = "adpe_v2_distributed"`)

---

### Sprint 4 — Provenance Verification Engine
**Route:** `POST /api/verify`  
**Service:** `verification_service.py`  
**Pipeline:**
```
Image upload → MultiRegion MIR extraction → pHash generation → DB lookup → Hamming distance → IntegrityAssessment → VerificationResult
```
**Integrity verdicts:** `AUTHENTIC` | `MODIFIED` | `UNVERIFIED`

---

### Sprint 5 — Multi-Region Extraction (already implemented)
**Service:** `provenance_extraction_service.py`  
Already performs full multi-region recovery loop with consistency checks + DCT fallback.

---

## Provenance Engine — Full File Map

```
services/
  ├── registration_service.py          # Sprint 1: Register image, store in DB
  ├── provenance_embedding_service.py  # Sprint 2–5: Orchestrate embedding
  ├── provenance_extraction_service.py # Sprint 3–5: Orchestrate extraction
  │
  ├── embedding/
  │   ├── embedding_strategy.py        # Abstract EmbeddingStrategy (ABC)
  │   ├── lsb_strategy.py             # Concrete: sequential LSB
  │   ├── binary_encoder.py           # Bytes → bitstream (with 32-bit length header)
  │   └── mir_serializer.py           # MediaIdentityRecord + serialize/build_mir
  │
  ├── extraction/
  │   ├── adpe_strategy.py            # Concrete: adaptive distributed strategy
  │   ├── binary_decoder.py           # Bitstream → bytes
  │   ├── bitstream_reader.py         # Read raw LSBs from image
  │   ├── mir_deserializer.py         # bytes → MediaIdentityRecord
  │   ├── payload_allocator.py        # Bit allocation across regions
  │   └── region_manager.py           # Adaptive grid partitioning
  │
  ├── verification/
  │   ├── verification_service.py     # End-to-end verification pipeline
  │   ├── hamming_distance.py         # pHash distance computation
  │   └── phash_service.py            # Perceptual hash generation
  │
  ├── integrity/
  │   └── integrity_service.py        # IntegrityAssessment scoring
  │
  └── dct/
      ├── dct_strategy.py             # DCT-QIM embedding (experimental)
      ├── dct_transform.py            # DCT computation
      ├── block_processor.py          # 8×8 block processing
      ├── coefficient_selector.py     # Mid-frequency coefficient selection
      ├── qim_embedder.py             # Quantization Index Modulation embed
      └── qim_extractor.py            # QIM extraction
```

---

## AI Forensics Engine (Layer 2) — Full File Map

```
services/ai_forensics/
  ├── __init__.py            # Public surface: DetectionResult, AIEvidenceResult, DetectionEngine
  ├── base_detector.py       # AIForensicDetector (ABC): name + analyze()
  ├── models.py              # DetectionResult, AIEvidenceResult (frozen dataclasses)
  ├── detection_engine.py    # Orchestrator: registry + run() + default()
  ├── fusion.py              # DetectionFusion: weighted ensemble → AIEvidenceResult
  │
  ├── detectors/
  │   ├── foundation_detector.py   # CLIP ViT-B/32 zero-shot (UnivFD approach)
  │   ├── statistical_detector.py  # Entropy, noise, edge density, skewness
  │   ├── artifact_detector.py     # LBP texture + Canny edges (CV-based)
  │   └── frequency_detector.py   # FFT grid + power law + JPEG forensics
  │
  ├── artifact/               # Sub-analyzers for ArtifactDetector
  │   ├── texture.py          # LBP, texture entropy, local variance CoV
  │   ├── edges.py            # Canny, Laplacian, edge continuity
  │   └── fusion.py           # ArtifactFusion (texture + edges)
  │
  ├── frequency/              # Sub-analyzers for FrequencyDetector
  │   ├── spectral_grid.py         # FFT checkerboard detection
  │   ├── power_law.py             # 1/f^α analysis
  │   ├── compression_forensics.py # JPEG block boundary analysis
  │   ├── spectral_utils.py        # Shared FFT utilities
  │   └── frequency_fusion.py      # FrequencyFusion combiner
  │
  └── utils/
      ├── image_statistics.py  # Entropy, noise, edge, histogram computations
      └── preprocessing.py     # Shared image preprocessing
```

---

## Detector Plugin Contract

```python
# The immutable interface every detector must satisfy:
class AIForensicDetector(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...   # Unique machine-readable ID

    @abstractmethod
    def analyze(self, image: Image.Image) -> DetectionResult: ...
```

```python
@dataclass(frozen=True)
class DetectionResult:
    engine:     str     # detector name
    score:      float   # [0.0=authentic, 1.0=AI-generated]
    confidence: float   # [0.0, 1.0]
    reason:     str     # human-readable explanation
    metadata:   dict    # extra diagnostics
```

**To add a new detector:** implement the ABC, register with `engine.register(MyDetector())` — zero other changes needed.

---

## Fusion Architecture

**Layer 2 (Intra-engine):**
- `DetectionFusion.fuse(results)` → `AIEvidenceResult`
- Weighted average of `score` and `confidence` across all detectors
- Default weights: `foundation_clip=0.60`, `statistical_features=0.20`, `artifact_cv=0.20`
- `frequency_spectral` is **commented out** of DEFAULT_WEIGHTS — it uses the `DEFAULT_WEIGHT=0.40` fallback

**Verdict thresholds on `AIEvidenceResult`:**
- `ai_probability < 0.40` → `AUTHENTIC`
- `0.40 ≤ ai_probability < 0.70` → `AMBIGUOUS`
- `ai_probability ≥ 0.70` → `AI_GENERATED`

---

## API Surface

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/api/register` | Register new AI-generated image |
| POST | `/api/embed` | Embed MIR provenance into registered image |
| POST | `/api/extract` | Extract provenance from embedded image |
| POST | `/api/verify` | Full verification pipeline |
| POST | `/api/forensics/analyze` | Run Layer 2 AI Forensics Engine |
| GET | `/api/forensics/status` | Engine health + plugin registry |
| GET | `/api/dct/...` | DCT experimental routes |
| GET | `/api/health` | System health check |

---

## Frontend

- **Framework:** React + Vite + Tailwind CSS
- **API layer:** `services/api.js` (Axios)
- **Pages:** `RegisterPage.jsx` (Sprint 1 UI, later expanded)
- **Components:** `Navbar`, `UploadZone`, `ModelSelector`, `RegistrationSuccess`
- The frontend is ahead of documentation — full pipeline likely has more pages than README shows.

---

## Robustness Benchmarks (existing data)

| Strategy | Distortion | Recovery |
|----------|-----------|----------|
| LSB-ADPE | PNG save | 100% ✅ |
| LSB-ADPE | JPEG / brightness / resize / noise | 0% ❌ |
| DCT-QIM | PNG save | 6.25% ✅ |
| DCT-QIM | JPEG 70–95% | 6.25% ✅ (87–84% similarity) |
| DCT-QIM | Brightness +10% | 6.25% ✅ |
| DCT-QIM | Resize / crop / heavy augmentation | 0% ❌ |

> Key insight: LSB-ADPE has **zero robustness** to any lossy transform. DCT-QIM shows moderate JPEG robustness but is limited to 6.25% regional recovery only.

---

## Architectural Observations & Inconsistencies

### ✅ Strong Points

1. **Plugin pattern is clean and consistently applied.** `AIForensicDetector` ABC enforces the contract rigorously. Engine is genuinely open for extension, closed for modification.

2. **Layered abstraction in provenance embedding.** `EmbeddingStrategy` ABC + DI in `embed_provenance()` is textbook OCP.

3. **Frozen dataclasses for data contracts.** `DetectionResult`, `AIEvidenceResult`, `MediaIdentityRecord` are all immutable — prevents accidental mutation across pipeline stages.

4. **Stateless engine.** `DetectionEngine.run()` is per-call stateless — safe for concurrent FastAPI requests.

5. **Graceful degradation.** Both `DetectionEngine` (detector failures) and `extract_provenance` (region failures) continue with remaining evidence. Good for production robustness.

6. **Separation of concerns.** Routes are thin (no business logic). Services own orchestration. Sub-analyzers are pure functions. Fusion is a separate concern.

### ⚠️ Architectural Observations (Not Bugs — Awareness Points)

1. **`frequency_spectral` not in DEFAULT_WEIGHTS dict.**
   - It falls back to `DEFAULT_WEIGHT = 0.40` in `fusion.py`.
   - The commented-out line in `DEFAULT_WEIGHTS` suggests this was intentional during development. Should be explicitly added with a calibrated weight once benchmarked.

2. **`adpe_strategy.py` lives in `extraction/` but implements `EmbeddingStrategy`.**
   - The embedding concern is in the wrong package. `ADPEStrategy` is imported by `provenance_embedding_service.py` from `app.services.extraction.adpe_strategy`.
   - This is a naming/placement inconsistency: the embedding strategy is in the extraction package.

3. **`requirements.txt` missing ML dependencies.**
   - `open_clip_torch`, `torch`, `numpy`, `scikit-image`, `scikit-learn`, `scipy` are all used but absent from `requirements.txt`. Likely installed separately/manually.

4. **DCT pipeline is "experimental" but integrated into the main extraction fallback.**
   - `provenance_extraction_service.py` has a DCT fallback in the main code path. This couples an experimental module into production logic. A feature flag or strategy abstraction would be cleaner.

5. **`IntegrityAssessment.score` is computed from `similarity` (which is a %).**
   - `similarity` from `hamming_distance.py` is in `[0, 100]`, and the `assess_integrity()` function subtracts penalties from it. The docstring and type hint say `int` for the score but the inputs are floats. Minor typing inconsistency.

6. **`VerificationResult` uses both `status` ("verified"/"unverified") and `verification` ("AUTHENTIC"/"MODIFIED"/"UNVERIFIED") as separate fields.**
   - These are semantically redundant. `MODIFIED` maps to `"verified"` overall_status, which is counterintuitive — a modified image shouldn't read as "verified".

7. **`on_event("startup")` / `on_event("shutdown")` are deprecated in FastAPI >= 0.93.**
   - Should be replaced with the `lifespan` context manager pattern.

---

## Current Implementation Status

| Component | File | Status |
|-----------|------|--------|
| Media Registration | `registration_service.py` | ✅ Complete |
| MIR Builder | `embedding/mir_serializer.py` | ✅ Complete |
| LSB Embedding | `embedding/lsb_strategy.py` | ✅ Complete |
| ADPE Embedding | `extraction/adpe_strategy.py` | ✅ Complete (Sprint 5 v2) |
| Multi-Region Extraction | `provenance_extraction_service.py` | ✅ Complete |
| Verification Pipeline | `verification/verification_service.py` | ✅ Complete |
| Integrity Assessment | `integrity/integrity_service.py` | ✅ Complete |
| DCT-QIM (experimental) | `dct/` | ✅ Implemented, limited robustness |
| Foundation Detector (CLIP) | `detectors/foundation_detector.py` | ✅ Complete |
| Statistical Detector | `detectors/statistical_detector.py` | ✅ Complete |
| Artifact Detector (CV) | `detectors/artifact_detector.py` | ✅ Complete |
| Frequency Detector | `detectors/frequency_detector.py` | ✅ Complete |
| Detection Fusion | `fusion.py` | ✅ Complete (weights need calibration) |
| Trust Score (Layer 3) | — | ❌ Not yet implemented |
| End-to-End Fusion | — | ❌ Not yet implemented |
| Detector Benchmarking | — | ❌ Not yet performed |
| Frontend (full pipeline UI) | `frontend/src/` | 🔶 Partial |
