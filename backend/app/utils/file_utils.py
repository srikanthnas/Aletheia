"""
File utility helpers — path management and sanitisation.
"""

import os
import re


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def get_file_extension(filename: str) -> str:
    """Return lowercase file extension without the leading dot."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def is_allowed_extension(filename: str) -> bool:
    """Return True only if the file extension is in the allowed set."""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


def sanitise_filename(filename: str) -> str:
    """
    Strip potentially dangerous characters from a filename.
    Keeps alphanumerics, dots, hyphens, and underscores.
    """
    name, _, ext = filename.rpartition(".")
    safe_name = re.sub(r"[^\w\-]", "_", name)
    return f"{safe_name}.{ext.lower()}"


def build_upload_path(upload_dir: str, image_id: str, filename: str) -> str:
    """
    Construct the absolute path where the uploaded image will be stored.
    The image is stored as: <upload_dir>/<image_id>_<filename>
    """
    safe_filename = sanitise_filename(filename)
    stored_name = f"{image_id}_{safe_filename}"
    return os.path.join(upload_dir, stored_name)
