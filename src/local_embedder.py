import os
from typing import List
from sentence_transformers import SentenceTransformer

_LOCAL_EMBED_MODEL = os.getenv("LOCAL_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_model = None

def embed_text(text: str) -> List[float]:
    global _model
    if _model is None:
        _model = SentenceTransformer(_LOCAL_EMBED_MODEL)
    vec = _model.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()
