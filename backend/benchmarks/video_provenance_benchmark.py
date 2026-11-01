"""Small CLI benchmark for temporal provenance recovery.

Usage:
    python -m benchmarks.video_provenance_benchmark <video>

This benchmark only measures the supplied video; it does not manufacture
robustness claims. It is intentionally independent from the web API.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from app.services.video.video_service import _probe, _extract_selected_frames, _extract_frame_bits
from app.services.dct.robust_codec import HEADER_SIZE, decode_header, frame_bit_length, decode_robust


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    args = parser.parse_args()
    info = _probe(args.video)
    count = min(20, max(10, int(info.duration * 2)))
    times = [info.duration * (i + 0.5) / count for i in range(count)]

    with tempfile.TemporaryDirectory(prefix="aletheia_video_benchmark_") as tmp:
        paths = _extract_selected_frames(args.video, tmp, times)
        successes = []
        for i, path in enumerate(paths):
            try:
                with Image.open(path) as im:
                    header = _extract_frame_bits(im, HEADER_SIZE * 14)
                    _, payload_len, _, _ = decode_header(header)
                    bits = _extract_frame_bits(im, frame_bit_length(payload_len))
                    payload, meta = decode_robust(bits)
                    mir = json.loads(payload.decode("utf-8"))
                    successes.append({"index": i, "time": times[i], "media_id": mir.get("media_id"), "corrected_codewords": meta["corrected_codewords"]})
            except Exception as exc:
                successes.append({"index": i, "time": times[i], "error": str(exc)})

    print(json.dumps({
        "video": str(Path(args.video)),
        "duration_seconds": info.duration,
        "fps": info.fps,
        "frames": info.frame_count,
        "scanned": count,
        "recovered": sum("media_id" in x for x in successes),
        "results": successes,
    }, indent=2))


if __name__ == "__main__":
    main()
