"""Unit tests for the V4 temporal provenance primitives."""
from app.services.video.video_service import (
    CHECKPOINT_FRACTIONS,
    _checkpoint_frames,
    _phash_distance,
    _temporal_fingerprint_score,
    VideoInfo,
)


def test_checkpoint_layout_is_temporal_and_deterministic():
    info = VideoInfo(duration=10.0, fps=24.0, frame_count=240, width=1280, height=720, has_audio=False)
    frames = _checkpoint_frames(info)
    assert len(frames) == 10
    assert frames == sorted(frames)
    assert all(0 <= f < info.frame_count for f in frames)


def test_phash_distance_is_hamming_distance():
    assert _phash_distance("0000000000000000", "0000000000000000") == 0
    assert _phash_distance("0000000000000000", "0000000000000001") == 1


def test_temporal_fingerprint_requires_multiple_matches():
    refs = ["0000000000000000", "0000000000000000"]
    score = _temporal_fingerprint_score(
        ["0000000000000000", "0000000000000000"],
        refs,
        threshold=4,
    )
    assert score["matches"] == 2
    assert score["match_rate"] == 1.0
