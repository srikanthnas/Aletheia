"""
metrics.py — Utilities for image quality assessment.
"""
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

def calculate_mse(original: Image.Image, reconstructed: Image.Image) -> float:
    """
    Calculates the Mean Squared Error (MSE) between two PIL images.
    """
    orig_arr = np.array(original, dtype=np.float32)
    recon_arr = np.array(reconstructed, dtype=np.float32)
    
    if orig_arr.shape != recon_arr.shape:
        raise ValueError("Images must have the same dimensions to calculate MSE.")
        
    mse = np.mean((orig_arr - recon_arr) ** 2)
    return float(mse)

def calculate_psnr(original: Image.Image, reconstructed: Image.Image) -> float:
    """
    Calculates the Peak Signal-to-Noise Ratio (PSNR) between two PIL images.
    Returns float('inf') if MSE is zero (images are identical).
    """
    mse = calculate_mse(original, reconstructed)
    if mse == 0:
        return float('inf')
        
    max_pixel = 255.0
    psnr = 20 * np.log10(max_pixel / np.sqrt(mse))
    return float(psnr)

def calculate_ssim(original: Image.Image, reconstructed: Image.Image) -> float:
    """
    Calculates the Structural Similarity Index (SSIM) between two PIL images.
    Returns a value between -1.0 and 1.0 (1.0 is identical).
    """
    orig_arr = np.array(original, dtype=np.uint8)
    recon_arr = np.array(reconstructed, dtype=np.uint8)
    
    if orig_arr.shape != recon_arr.shape:
        raise ValueError("Images must have the same dimensions to calculate SSIM.")
        
    if orig_arr.ndim == 3 and orig_arr.shape[-1] == 3:
        # Multichannel RGB image
        return float(ssim(orig_arr, recon_arr, channel_axis=2))
    elif orig_arr.ndim == 2:
        # Grayscale image
        return float(ssim(orig_arr, recon_arr))
    else:
        raise ValueError("Unsupported image format for SSIM.")
