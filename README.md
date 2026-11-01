# Aletheia

Aletheia is a research framework for media provenance and integrity. It provides
tools to register images and videos, embed provenance data, recover and verify
that data, and analyze images for signals associated with AI generation.

> **Research prototype:** Provenance recovery and forensic analysis are
> experimental. Results depend on the media, transformations, and available
> reference records; Aletheia does not guarantee that media is authentic or
> tamper-proof.

## Features

- **Image registration:** Store an image and its declared generative model in a
  MongoDB registry.
- **Image provenance:** Embed a Media Identity Record (MIR) in an image, extract
  it, and compare the recovered provenance and image integrity with registry
  data. The standard image workflow uses LSB embedding; a separate DCT-QIM
  workflow is available for experimentation.
- **AI forensics:** Analyze image content using the available forensic
  detectors, independently of whether Aletheia provenance is present.
- **Video provenance:** Register videos, embed temporal provenance checkpoints,
  download an FFV1/MKV artifact, and verify provenance and temporal consistency.
- **Benchmarking:** Run image-forensics and provenance robustness benchmarks
  with the included scripts and demo assets.

## Project layout

```text
backend/
  app/
    api/routes/       FastAPI endpoints
    services/         Registration, embedding, extraction, verification,
                      forensics, trust, and video workflows
    schemas/          API request and response models
  benchmarks/         Benchmark and validation scripts
  tests/              Backend tests
  requirements.txt
demo_assets/           Example images and dataset utilities
frontend/
  src/                 React application
  package.json
```

## Requirements

- Python 3.10 or newer
- Node.js and npm
- MongoDB
- FFmpeg and FFprobe on `PATH` for video workflows

## Run locally

### 1. Start MongoDB

Start a local MongoDB server, or configure `MONGODB_URL` to use another
MongoDB instance.

### 2. Install and start the backend

From the project root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On macOS or Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

The backend connects to MongoDB at startup. Interactive API documentation is
available at [http://localhost:8000/api/docs](http://localhost:8000/api/docs);
ReDoc is at [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc).

### 3. Install and start the frontend

In a second terminal, from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite development
server proxies `/api` requests to `http://localhost:8000`.

## Configuration

The backend reads these settings from environment variables or a `.env` file
in its working directory. Defaults are shown below.

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection URL |
| `DATABASE_NAME` | `aletheia_db` | MongoDB database name |
| `UPLOAD_DIR` | `app/uploads` | Directory for uploaded and generated media |
| `FRAMEWORK_VERSION` | `1.0` | Version recorded in provenance metadata |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Allowed frontend origin |

The frontend API base URL defaults to `http://localhost:8000`. Set
`VITE_API_URL` at frontend build or development time to override it.

## Main API workflows

All routes are prefixed with `/api`; the interactive API docs list the current
request and response schemas.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check backend status |
| `POST` | `/api/register` | Register an image and its model name |
| `POST` | `/api/embed` | Embed provenance into a registered image |
| `POST` | `/api/extract` | Extract provenance from an embedded image |
| `POST` | `/api/verify` | Verify an embedded image against registry data |
| `POST` | `/api/assess` | Run the combined image assessment workflow |
| `POST` | `/api/forensics/analyze` | Run standalone AI-forensics analysis |
| `GET` | `/api/forensics/status` | Inspect available forensic detectors |
| `POST` | `/api/video/register` | Register a video |
| `POST` | `/api/video/embed` | Embed video provenance for a registered video |
| `GET` | `/api/video/download/{video_id}` | Download the embedded video artifact |
| `POST` | `/api/video/verify` | Verify video provenance |
| `POST` | `/api/dct/embed` | Experiment with DCT-QIM image embedding |
| `POST` | `/api/dct/extract` | Extract an experimental DCT-QIM payload |

The usual image flow is **register → embed → extract or verify**. The standard
image embedding and extraction workflow uses PNG; lossy conversions such as
JPEG can damage the embedded payload. Video registration and embedding require
FFmpeg and FFprobe to be installed and accessible to the backend process.

## Tests and checks

Run the backend tests from the `backend` directory (install `pytest` in the
active environment if it is not already available):

```bash
python -m pytest tests
```

Run the frontend lint and production build from the `frontend` directory:

```bash
npm run lint
npm run build
```

## Demo assets and benchmarks

Example images are in [`demo_assets/`](demo_assets/). Dataset guidance and
utility instructions are in [`demo_assets/README.md`](demo_assets/README.md).
Benchmark and validation scripts are in `backend/benchmarks/`; run scripts
from the `backend` directory unless their instructions say otherwise.

## Further reading

- [Video provenance design](VIDEO_PROVENANCE_V4.md)
- [Architecture analysis](aletheia_architecture_analysis.md)
- [Robustness benchmark notes](backend/benchmark_robustness.md)
