"""
app/services/embedding/__init__.py

Public surface of the embedding sub-package.

Importing from this module is the correct way for other services
to access embedding components — internal module organisation
can change without breaking callers.
"""

from app.services.embedding.embedding_strategy import EmbeddingStrategy
from app.services.embedding.lsb_strategy import LSBStrategy
from app.services.embedding.mir_serializer import MediaIdentityRecord, build_mir, serialize
from app.services.embedding.binary_encoder import encode, decode

__all__ = [
    "EmbeddingStrategy",
    "LSBStrategy",
    "MediaIdentityRecord",
    "build_mir",
    "serialize",
    "encode",
    "decode",
]
