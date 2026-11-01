"""
coefficient_selector.py — Configuration and selection of DCT mid-frequency coefficients.
"""

# These coordinates represent mid-frequency components in an 8x8 DCT block.
# Format: (row, col)
# We avoid (0,0) (DC coefficient) as modifying it alters visual brightness significantly.
# We avoid high-frequency coefficients (bottom-right) as they are easily destroyed 
# by JPEG compression and low-pass filtering.
MID_FREQUENCY_INDEXES = [
    (1, 2), (2, 1), (0, 3), (3, 0),
    (2, 2), (1, 3), (3, 1), (0, 4),
    (4, 0), (2, 3), (3, 2), (1, 4)
]

def get_embeddable_coefficients() -> list[tuple[int, int]]:
    """
    Returns the configured list of (row, col) tuples representing the 
    mid-frequency DCT coefficients suitable for robust embedding.
    """
    return MID_FREQUENCY_INDEXES
