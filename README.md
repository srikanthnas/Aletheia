# Aletheia — AI Media Provenance Framework

> **Sprint 1 · Media Registration Engine**

Aletheia is a lightweight AI Media Provenance Framework for registering, preserving, and later verifying the authenticity of AI-generated media.

---

## Project Architecture

```
Aletheia/
├── backend/                        # FastAPI Python backend
│   ├── app/
│   │   ├── api/routes/             # Thin HTTP route handlers
│   │   │   └── registration.py
│   │   ├── core/                   # Configuration
│   │   │   └── config.py
│   │   ├── database/               # MongoDB connection lifecycle
│   │   │   └── connection.py
│   │   ├── models/                 # DB document models
│   │   │   └── media.py
│   │   ├── schemas/                # API request/response schemas
│   │   │   └── registration.py
│   │   ├── services/               # Business logic (registration_service)
│   │   │   └── registration_service.py
│   │   ├── utils/                  # Helpers (file_utils)
│   │   │   └── file_utils.py
│   │   ├── uploads/                # Stored image files
│   │   └── main.py                 # App entry point
│   ├── .env
│   └── requirements.txt
│
└── frontend/                       # React + Vite + Tailwind CSS
    ├── src/
    │   ├── components/             # Reusable UI components
    │   │   ├── Navbar.jsx
    │   │   ├── UploadZone.jsx
    │   │   ├── ModelSelector.jsx
    │   │   └── RegistrationSuccess.jsx
    │   ├── pages/
    │   │   └── RegisterPage.jsx
    │   ├── services/
    │   │   └── api.js              # Axios HTTP layer
    │   ├── App.jsx
    │   └── main.jsx
    ├── .env
    └── tailwind.config.js
```

---

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB running locally on port `27017`

### 1. Start MongoDB
```bash
mongod
```

### 2. Start the Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/api/docs

### 3. Start the Frontend
```bash
cd frontend
npm run dev
```

UI available at: http://localhost:5173

---

## API Reference

### `POST /api/register`

Register an AI-generated media asset.

**Content-Type:** `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `file` | File | PNG / JPG / JPEG image |
| `model_name` | string | AI model that generated the image |

**Response:**
```json
{
  "status": "success",
  "message": "Media registered successfully.",
  "metadata": {
    "image_id": "uuid-v4",
    "model_name": "Stable Diffusion XL",
    "timestamp": "2026-07-02T08:00:00+00:00",
    "media_type": "image",
    "framework_version": "1.0"
  }
}
```

---

## Database

**Collection:** `registered_media`

| Field | Type | Description |
|-------|------|-------------|
| `image_id` | string | UUID v4 |
| `filename` | string | Original filename |
| `model_name` | string | Generative AI model |
| `timestamp` | string | ISO-8601 UTC timestamp |
| `media_type` | string | `"image"` |
| `framework_version` | string | `"1.0"` |
| `upload_path` | string | Server-side file path |

---

## Roadmap

| Sprint | Engine | Status |
|--------|--------|--------|
| 1 | Media Registration Engine | ✅ Complete |
| 2 | Media Verification Engine | 🔜 Planned |
| 3 | Provenance Integrity Assessment Engine | 🔜 Planned |


---

## V4 — Temporal Video Provenance

V4 preserves the complete V3 image pipeline and adds a separate video provenance layer.

### Video capabilities
- Video registration with duration, FPS, frame count and dimensions.
- Ten deterministic temporal provenance checkpoints.
- ±1-frame temporal redundancy around each checkpoint.
- DCT-domain temporal provenance modulation.
- Existing Aletheia robust Hamming(7,4) + CRC32 + interleaving payload codec.
- Lossless FFV1/gbrp artifact generation for exact embedded-signal preservation.
- Temporal scanning during verification.
- Perceptual temporal fingerprinting as a persistence/source-identification fallback
  when embedded provenance is lost after lossy distribution.
- Coarse temporal mismatch/tamper windows.
- Video verification API:
  - `POST /api/video/register`
  - `POST /api/video/embed`
  - `POST /api/video/verify`

### Research position
The V4 video layer is intentionally designed around a real-world distribution
problem: provenance may be degraded or stripped after re-encoding, resizing,
trimming or editing. Aletheia therefore separates **provenance recovery** from
**source identity** and **integrity assessment**.

The system does not claim absolute tamper-proofing. Robustness is an empirical
research question and should be evaluated using the V4 video attack benchmark.

### Frontend
A small **Video Provenance** tab was added to the existing V3 interface.
The existing image registration, embedding, verification and analysis components
are left unchanged.
