import numpy as np
from PIL import Image

def get_ycbcr_channels(image: Image.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Converts a PIL Image to YCbCr color space.
    Returns the Y, Cb, and Cr channels as numpy arrays.
    Y channel is returned as float32 for precision during DCT.
    """
    ycbcr = image.convert('YCbCr')
    y, cb, cr = ycbcr.split()
    return np.array(y, dtype=np.float32), np.array(cb), np.array(cr)

def get_blocks_8x8(y_channel: np.ndarray) -> list[np.ndarray]:
    """
    Divides the Y channel into an ordered list of 8x8 blocks.
    Ignores boundary pixels that do not form a complete 8x8 block.
    """
    h, w = y_channel.shape
    h_adj = (h // 8) * 8
    w_adj = (w // 8) * 8
    
    blocks = []
    for i in range(0, h_adj, 8):
        for j in range(0, w_adj, 8):
            block = y_channel[i:i+8, j:j+8].copy()
            blocks.append(block)
    return blocks

def reconstruct_y_channel(blocks: list[np.ndarray], original_y: np.ndarray) -> np.ndarray:
    """
    Reconstructs the Y channel from processed 8x8 blocks.
    The original_y array is used to preserve any boundary pixels that 
    were not part of the 8x8 grid.
    """
    y_recon = original_y.copy()
    h, w = y_recon.shape
    h_adj = (h // 8) * 8
    w_adj = (w // 8) * 8
    
    block_idx = 0
    for i in range(0, h_adj, 8):
        for j in range(0, w_adj, 8):
            y_recon[i:i+8, j:j+8] = blocks[block_idx]
            block_idx += 1
            
    return y_recon

def reconstruct_image(y_channel: np.ndarray, cb: np.ndarray, cr: np.ndarray) -> Image.Image:
    """
    Recombines the modified Y channel with the original Cb and Cr channels,
    and returns a reconstructed RGB PIL Image.
    """
    y_clipped = np.clip(y_channel, 0, 255).astype(np.uint8)
    
    y_img = Image.fromarray(y_clipped, mode='L')
    cb_img = Image.fromarray(cb, mode='L')
    cr_img = Image.fromarray(cr, mode='L')
    
    ycbcr = Image.merge('YCbCr', (y_img, cb_img, cr_img))
    return ycbcr.convert('RGB')
