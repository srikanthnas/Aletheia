"""
frequency — Frequency-domain analysis for AI artifact detection.

This module provides spectral analysis tools for detecting AI-generated images
through frequency-domain signatures:

  * Spectral grid patterns (GAN upsampling artifacts)
  * Power law deviation (natural image statistics)
  * Compression fingerprints (JPEG block boundary analysis)

Public Interface
----------------
- SpectralGridAnalyzer    : Detects GAN checkerboard artifacts via FFT
- PowerLawAnalyzer        : Analyzes 1/f^α natural statistics
- CompressionForensicsAnalyzer : Analyzes JPEG compression fingerprints
- FrequencyFusion         : Weighted combination of frequency analyzers

Architecture
------------
This module mirrors the `artifact/` module architecture:
  - Each analyzer is independent and testable
  - FrequencyFusion combines results with configurable weights
  - All analyzers return: {score, confidence, features, flags}
"""

from app.services.ai_forensics.frequency.spectral_grid import SpectralGridAnalyzer
from app.services.ai_forensics.frequency.power_law import PowerLawAnalyzer
from app.services.ai_forensics.frequency.compression_forensics import (
    CompressionForensicsAnalyzer,
)
from app.services.ai_forensics.frequency.frequency_fusion import FrequencyFusion

__all__ = [
    "SpectralGridAnalyzer",
    "PowerLawAnalyzer",
    "CompressionForensicsAnalyzer",
    "FrequencyFusion",
]
