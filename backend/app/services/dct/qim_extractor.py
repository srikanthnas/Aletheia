"""
qim_extractor.py — Extracts bits embedded using QIM in the frequency domain.
"""
from PIL import Image

from app.services.dct.block_processor import get_ycbcr_channels, get_blocks_8x8
from app.services.dct.dct_transform import forward_dct_8x8
from app.services.dct.coefficient_selector import get_embeddable_coefficients
from app.services.dct.qim_embedder import extract_bit
from app.services.dct.distributed_layout import DCTRegion

def extract_bitstream(image: Image.Image, q_step: float = 16.0, max_bits: int | None = None) -> list[int]:
    """
    Extracts the full bitstream embedded in the image using DCT and QIM.
    
    Args:
        image: The PIL Image potentially containing a watermark.
        q_step: The quantization step size used during embedding.
        max_bits: Optional limit on how many bits to extract to save CPU time.
        
    Returns:
        A list of extracted bits (0s and 1s).
    """
    y_channel, _, _ = get_ycbcr_channels(image)
    blocks = get_blocks_8x8(y_channel)
    coefficients = get_embeddable_coefficients()
    
    bitstream = []
    
    for block in blocks:
        # Level shifting matching the embedding process
        shifted_block = block - 128.0
        
        # Forward DCT
        dct_coeffs = forward_dct_8x8(shifted_block)
        
        # Extract bit from each configured coefficient (RDM — pass block as context)
        for (r, c) in coefficients:
            bit = extract_bit(dct_coeffs[r, c], step=q_step, context=dct_coeffs)
            bitstream.append(bit)
            if max_bits is not None and len(bitstream) >= max_bits:
                return bitstream
                
    return bitstream


def extract_region_bitstream(image: Image.Image, q_step: float = 16.0, max_bits: int | None = None) -> list[int]:
    """Extract DCT-QIM bits from one regional carrier."""
    return extract_bitstream(image, q_step=q_step, max_bits=max_bits)
