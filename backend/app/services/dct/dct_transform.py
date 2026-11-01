import numpy as np
from scipy.fftpack import dct, idct

def forward_dct_8x8(block: np.ndarray) -> np.ndarray:
    """
    Applies the 2D Forward Discrete Cosine Transform to an 8x8 block.
    Uses 'ortho' normalization to ensure a mathematically correct and 
    energy-preserving transform.
    """
    # Apply 1D DCT along rows, then 1D DCT along columns
    return dct(dct(block, axis=0, norm='ortho'), axis=1, norm='ortho')

def inverse_dct_8x8(dct_block: np.ndarray) -> np.ndarray:
    """
    Applies the 2D Inverse Discrete Cosine Transform to an 8x8 DCT block.
    Uses 'ortho' normalization.
    """
    # Apply 1D IDCT along rows, then 1D IDCT along columns
    return idct(idct(dct_block, axis=0, norm='ortho'), axis=1, norm='ortho')
