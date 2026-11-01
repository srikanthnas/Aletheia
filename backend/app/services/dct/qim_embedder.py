"""
qim_embedder.py — Rational Dither Modulation (RDM) for frequency-domain embedding.

Background
----------
Standard Quantization Index Modulation (QIM) quantizes an absolute AC coefficient
value. A uniform gain attack (brightness, contrast) multiplies every AC coefficient
by a scale factor α, shifting the value across QIM decision boundaries and causing
catastrophic bit-error rates.

Rational Dither Modulation (RDM) — Pérez-Freire et al., IEEE Trans. Information
Forensics & Security, 2006 — removes this sensitivity by normalizing the coefficient
against a *local gain reference* g(X) before quantization:

    r = x / g(X)

If the image is scaled by α:
    r' = (α·x) / (α·g(X)) = x / g(X) = r       ← gain cancels perfectly

The gain reference g(X) is the L2 norm of a small set of stable low-to-mid
frequency coefficients from the same 8×8 DCT block (NORM_POSITIONS below).  These
positions are deliberately chosen to NOT overlap with the embedding positions in
coefficient_selector.py (MID_FREQUENCY_INDEXES).

Backward compatibility
----------------------
embed_bit() and extract_bit() accept an optional `context` keyword argument.
When context is None (the default), both functions fall back to standard QIM,
so any existing caller that does not supply context continues to work unchanged.
"""

import math
import numpy as np

# Low-frequency DCT positions used solely as the normalization reference.
# Must NOT overlap with MID_FREQUENCY_INDEXES in coefficient_selector.py.
# We explicitly EXCLUDE the DC coefficient (0,0) because brightness attacks add
# a uniform offset in the spatial domain, which shifts the DC coefficient linearly.
# By using ONLY AC coefficients, the norm g(X) becomes perfectly invariant to
# both brightness (additive) and contrast (multiplicative) attacks.
_NORM_POSITIONS: list[tuple[int, int]] = [(0, 1), (1, 0), (1, 1), (0, 2), (2, 0)]

# Floor on the norm to prevent division by zero and relative-error explosion for flat blocks.
# If g(X) is very small (e.g. 5.0), a ±1 quantization noise is a 20% relative error,
# which destroys the normalized coordinate r. Clamping it to 60.0 caps relative error
# at ~1.6%, ensuring convergence for lossless recovery while acting as standard QIM
# on near-zero coefficients (where gain attacks have minimal absolute effect anyway).
_NORM_FLOOR: float = 60.0

# Scale factor to bring the expected value of g(X) to roughly 1.0.
# The L2 norm of the 5 lowest AC coefficients averages around 120.
_NORM_SCALE: float = 120.0


def _compute_norm(dct_block: np.ndarray) -> float:
    """
    Compute the L2 norm of the normalization reference coefficients for one
    8×8 DCT block.  This is the gain reference g(X) in the RDM formulation.

    Args:
        dct_block: The 8×8 numpy array of DCT coefficients (level-shifted).

    Returns:
        A positive float representing g(X).  Never less than _NORM_FLOOR / _NORM_SCALE.
    """
    squared_sum = sum(float(dct_block[r, c]) ** 2 for (r, c) in _NORM_POSITIONS)
    norm = math.sqrt(squared_sum)
    return max(norm, _NORM_FLOOR) / _NORM_SCALE


def embed_bit(
    value: float,
    bit: int,
    step: float = 16.0,
    *,
    context: "np.ndarray | None" = None,
) -> float:
    """
    Embeds a single bit into a DCT coefficient using Rational Dither Modulation (RDM).

    When `context` (the full 8×8 DCT block) is provided, RDM is applied:
      1. Normalize the coefficient: r = value / g(context)
      2. Apply standard QIM on the normalized value r to produce r_q
      3. Denormalize: return r_q * g(context)

    When `context` is None, standard QIM is applied directly on `value`
    (backward-compatible fallback).

    Bit 0: quantize to nearest even multiple of step (in normalized domain).
    Bit 1: quantize to nearest odd  multiple of step (in normalized domain).

    Args:
        value:   The original float DCT coefficient.
        bit:     The bit to embed (0 or 1).
        step:    The quantization step size (higher = more robust, more distortion).
        context: Optional full 8×8 DCT block (numpy array).  Enables RDM.

    Returns:
        The quantized (and denormalized) coefficient.
    """
    if bit not in (0, 1):
        raise ValueError(f"Bit must be 0 or 1, got {bit}")

    if context is not None:
        # --- RDM path ---
        g = _compute_norm(context)
        r = value / g                                    # normalize

        # Standard QIM on the normalized value
        q_even = round(r / (2 * step)) * (2 * step)
        q_odd  = round((r - step) / (2 * step)) * (2 * step) + step
        r_q = q_even if bit == 0 else q_odd

        return float(r_q * g)                           # denormalize
    else:
        # --- Standard QIM fallback (backward compatible) ---
        q_even = round(value / (2 * step)) * (2 * step)
        q_odd  = round((value - step) / (2 * step)) * (2 * step) + step
        return float(q_even) if bit == 0 else float(q_odd)


def extract_bit(
    value: float,
    step: float = 16.0,
    *,
    context: "np.ndarray | None" = None,
) -> int:
    """
    Extracts a single bit from an RDM-quantized DCT coefficient.

    When `context` is provided, normalizes the coefficient before the QIM
    decision (must match the normalization used at embed time).

    When `context` is None, falls back to standard QIM extraction.

    Args:
        value:   The quantized float coefficient.
        step:    The quantization step size used during embedding.
        context: Optional full 8×8 DCT block (numpy array).  Enables RDM.

    Returns:
        0 if the coefficient is closer to an even multiple, 1 if odd.
    """
    if context is not None:
        # --- RDM path ---
        g = _compute_norm(context)
        r = value / g                                    # normalize
        quantized_index = round(r / step)
        return int(quantized_index % 2)
    else:
        # --- Standard QIM fallback (backward compatible) ---
        quantized_index = round(value / step)
        return int(quantized_index % 2)

