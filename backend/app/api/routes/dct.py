"""
api/routes/dct.py — Experimental DCT embedding and extraction routes.
"""
import io
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from PIL import Image

from app.services.dct.dct_strategy import DCTStrategy
from app.utils.metrics import calculate_psnr, calculate_mse
from app.services.embedding.mir_serializer import build_mir, serialize
from app.services.embedding.binary_encoder import encode
from app.services.dct.qim_extractor import extract_bitstream
from app.services.extraction.binary_decoder import bits_to_bytes
from app.services.extraction.mir_deserializer import deserialize
from app.core.config import settings

router = APIRouter()

@router.post(
    "/embed",
    summary="Embed MIR using DCT-QIM",
    description="Embeds provenance data into the frequency domain using QIM."
)
async def dct_embed(
    file: UploadFile = File(...),
    image_id: str = Form(default=None)
):
    contents = await file.read()
    try:
        original_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}")
        
    # Generate an MIR if not provided
    media_id = image_id or str(uuid.uuid4())
    mir = build_mir(
        media_id=media_id,
        model_name="Experimental DCT",
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    payload = serialize(mir)
    bitstream = encode(payload)
    
    strategy = DCTStrategy()
    capacity = strategy.capacity(original_image)
    if len(bitstream) > capacity:
        raise HTTPException(
            status_code=422,
            detail=f"Image capacity ({capacity} bits) insufficient for payload ({len(bitstream)} bits)."
        )
        
    embedded_image = strategy.embed(original_image, bitstream)
    
    # Save the embedded image
    filename = f"dct_{media_id}_embedded.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    embedded_image.save(filepath, format="PNG", optimize=False)
    
    psnr = calculate_psnr(original_image, embedded_image)
    mse = calculate_mse(original_image, embedded_image)
    
    return {
        "status": "success",
        "download_url": f"/uploads/{filename}",
        "psnr": round(psnr, 4),
        "mse": round(mse, 4),
        "capacity_used": len(bitstream),
        "total_capacity": capacity
    }


@router.post(
    "/extract",
    summary="Extract MIR using DCT-QIM",
    description="Extracts frequency-domain provenance data."
)
async def dct_extract(
    file: UploadFile = File(...)
):
    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}")
        
    bitstream = extract_bitstream(image, q_step=16.0)
    
    if len(bitstream) < 32:
        raise HTTPException(status_code=422, detail="Insufficient bits extracted for header.")
        
    # Read 32-bit header
    n_bytes = 0
    for bit in bitstream[:32]:
        n_bytes = (n_bytes << 1) | bit
        
    payload_bits_needed = n_bytes * 8
    if len(bitstream) < 32 + payload_bits_needed:
        raise HTTPException(status_code=422, detail="Extracted bitstream too short for declared payload.")
        
    payload_bits = bitstream[32 : 32 + payload_bits_needed]
    try:
        payload_bytes = bits_to_bytes(payload_bits)
        mir = deserialize(payload_bytes)
        return {
            "status": "success",
            "extraction_success": True,
            "recovered_bits": len(payload_bits) + 32,
            "recovered_mir": mir.to_dict()
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to deserialize MIR: {exc}")
