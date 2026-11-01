# Aletheia V4 — Temporal Video Provenance

## Research objective

Aletheia V4 extends the V3 image provenance foundation to video. The goal is
**transformation-resilient provenance**, not an absolute claim of tamper-proofing.

The video verifier separates:

1. **Origin / provenance** — can an Aletheia MIR be recovered?
2. **Source identity** — does the recovered media ID belong to a registered video?
3. **Temporal persistence** — how many sampled temporal positions retain the signal?
4. **Integrity interpretation** — does the current video differ structurally from the registered asset?

## Method

- Register video metadata (duration, FPS, dimensions, frame count).
- Derive ten deterministic temporal checkpoints at 5%, 15%, …, 95%.
- Build the existing Aletheia MIR with `media_type=video`.
- Encode the MIR with the existing robust Hamming(7,4) + CRC32 + interleaving codec.
- Embed the complete robust payload redundantly into the selected frames using the
  a video-specific DCT mid-frequency modulation primitive.
- Reconstruct an initial lossless FFV1/gbrp artifact so the embedded signal is
  preserved without an RGB/YUV conversion at the output boundary.
- Verification scans a temporal grid rather than requiring the original absolute
  checkpoint timestamps. This allows recovery attempts after trimming or other
  temporal shifts.
- The dominant recovered media ID is compared with the registered video registry.

## Why this is different from sequential LSB

Sequential LSB + FFV1 is a useful baseline: it demonstrates exact recovery in a
lossless pipeline. It is not sufficient as the final persistence method because
lossy distribution can alter pixel values and destroy LSBs.

V4 therefore uses the same frequency-domain DCT-QIM/RDM foundation already
validated for images and adds **temporal redundancy**.

## Evaluation protocol

The V4 benchmark should compare the baseline and robust method under:

- H.264 / H.265 re-encoding
- bitrate reduction
- resizing
- frame-rate conversion
- trimming
- frame deletion / duplication
- brightness / contrast changes
- blur / noise
- local spatial edits
- combined transformations

Report at minimum:

- provenance recovery rate
- source attribution accuracy
- temporal checkpoint recovery rate
- false attribution rate
- false rejection rate
- tamper localization error
- PSNR / SSIM / VMAF where available
- encoding and verification time

The benchmark must report **actual measured values**; no robustness guarantee is
claimed before those experiments are run.

## API

- `POST /api/video/register`
- `POST /api/video/embed`
- `POST /api/video/verify`

The image endpoints and image implementation are intentionally left unchanged.

## Frontend

V4 adds one small `Video Provenance` tab. Existing image registration,
verification, and analysis components are not modified.
