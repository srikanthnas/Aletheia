/**
 * API service layer — all HTTP calls go through here.
 * Keeps components decoupled from axios / endpoint URLs.
 *
 * Sprint 1: registerMedia()
 * Sprint 2: embedMedia()
 * Sprint 3: extractProvenance()
 * Sprint 4: verifyMedia()
 * Layer 3:  assessMedia()  — full end-to-end assessment
 */

import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
});

/* ─────────────────────────────────────────────────────────────────────────
   Sprint 1 — Registration
   ───────────────────────────────────────────────────────────────────────── */

/**
 * POST /api/register
 *
 * @param {File}   file       - The image file to register
 * @param {string} modelName  - The AI model that generated the image
 * @returns {Promise<Object>} - The registration response from the API
 */
export async function registerMedia(file, modelName) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("model_name", modelName);

  const { data } = await api.post("/api/register", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return data;
}

/* ─────────────────────────────────────────────────────────────────────────
   Sprint 2 — Provenance Embedding
   ───────────────────────────────────────────────────────────────────────── */

/**
 * POST /api/embed
 *
 * Triggers provenance embedding for a previously registered image.
 * The server retrieves the image, builds the MIR, and embeds it via LSB.
 *
 * @param {string} imageId - UUID returned by POST /api/register
 * @returns {Promise<Object>} - { status, embedded_image, embedded_bits }
 */
export async function embedMedia(imageId) {
  const { data } = await api.post("/api/embed", { image_id: imageId });
  return data;
}

/* ─────────────────────────────────────────────────────────────────────────
   Sprint 3 — Provenance Extraction
   ───────────────────────────────────────────────────────────────────────── */

/**
 * POST /api/extract
 *
 * Fetches the embedded PNG from the backend via the Vite dev proxy, then
 * uploads it as a multipart file to the extraction endpoint, which reads
 * the LSB bitstream and recovers the embedded Media Identity Record (MIR).
 *
 * @param {string} embeddedImageUrl - Full URL to the embedded PNG
 *                                    (constructed in EmbedPanel from result.embedded_image)
 * @returns {Promise<Object>} - { status, strategy_used, mir }
 */
export async function extractProvenance(embeddedImageUrl) {
  // 1. Fetch the embedded image as a binary blob through the Vite proxy
  const imgResponse = await fetch(embeddedImageUrl);
  if (!imgResponse.ok) {
    throw new Error(
      `Failed to fetch embedded image (HTTP ${imgResponse.status}). ` +
        "Ensure the backend is running and the image was saved successfully."
    );
  }
  const blob = await imgResponse.blob();

  // 2. Upload the blob to POST /api/extract as a multipart file
  const formData = new FormData();
  formData.append("file", blob, "embedded_image.png");

  const { data } = await api.post("/api/extract", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return data;
}

/* ─────────────────────────────────────────────────────────────────────────
   Sprint 4 — Provenance Verification
   ───────────────────────────────────────────────────────────────────────── */

/**
 * POST /api/verify
 *
 * Uploads an embedded image file to the verification endpoint.
 * The server extracts the MIR, generates pHash, computes Hamming Distance,
 * and returns a full verification report.
 *
 * @param {File} imageFile - The embedded PNG to verify
 * @returns {Promise<Object>} - Full verification report
 */
export async function verifyMedia(imageFile) {
  const formData = new FormData();
  formData.append("file", imageFile);

  const { data } = await api.post("/api/verify", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return data;
}

/* ─────────────────────────────────────────────────────────────────────────
   Layer 3 — Full End-to-End Assessment (Trust & Decision Engine)
   ───────────────────────────────────────────────────────────────────────── */

/**
 * POST /api/assess
 *
 * Runs the complete Aletheia three-layer pipeline:
 *   Layer 2 — AI Forensics (CLIP + Statistical + Artifact + Frequency)
 *   Layer 1 — Provenance Extraction + Verification
 *   Layer 3 — Trust & Decision Engine
 *
 * Does NOT require prior registration. Provenance extraction is attempted
 * blind and gracefully fails if no Aletheia watermark is present.
 *
 * @param {File} imageFile - The image to analyze (PNG recommended for embedded images)
 * @returns {Promise<Object>} - Full TrustResponse including verdict, score, and evidence
 */
export async function assessMedia(imageFile) {
  const formData = new FormData();
  formData.append("file", imageFile);

  const { data } = await api.post("/api/assess", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60_000, // CLIP inference may take longer than the default 30s
  });

  return data;
}

export default api;


/* ─────────────────────────────────────────────────────────────────────────
   V4 — Temporal Video Provenance
   ───────────────────────────────────────────────────────────────────────── */

export async function registerVideo(file, modelName) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("model_name", modelName);
  const { data } = await api.post("/api/video/register", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120_000,
  });
  return data;
}

export async function embedVideo(videoId) {
  const formData = new FormData();
  formData.append("video_id", videoId);
  const { data } = await api.post("/api/video/embed", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300_000,
  });
  return data;
}

export async function verifyVideo(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/api/video/verify", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 180_000,
  });
  return data;
}
