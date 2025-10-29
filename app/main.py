import base64
import os
import re
import time
from typing import Optional, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from app.crypto import decrypt_json, encrypt_json
from app.extractor import pdf_to_text_bytes

app = FastAPI(title="PDF2Text Encrypted Service", version="1.0.0")

# --- Sécurité / config ---
SHARED_KEY_B64 = os.getenv("SHARED_KEY_B64")  # base64 d'une clé 32 octets
if not SHARED_KEY_B64:
    raise RuntimeError("Missing SHARED_KEY_B64 env var (base64 of 32-byte key).")

MAX_MB = float(os.getenv("MAX_MB", "15"))  # limite taille PDF
TIMEOUT = int(os.getenv("FETCH_TIMEOUT", "30"))
ALLOWED_HOSTS_REGEX = os.getenv("ALLOWED_HOSTS_REGEX", r".*")  # ex: r"^https://.*\.hubspotusercontent-.*\.net/.*$"

# CORS (désactivé par défaut; utile si tu testes depuis un navigateur)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if os.getenv("CORS_ALLOW_ORIGINS") else [],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["*"],
)

class EncryptedPayload(BaseModel):
    cipher: str = Field(..., description="Base64(ciphertext) de l'objet JSON chiffré")

def _validate_url(u: str) -> None:
    if not re.match(ALLOWED_HOSTS_REGEX, u):
        raise HTTPException(400, detail="URL not allowed by ALLOWED_HOSTS_REGEX")

def _fetch_pdf(url: str) -> bytes:
    with requests.get(url, stream=True, timeout=TIMEOUT) as r:
        if r.status_code != 200:
            raise HTTPException(502, detail=f"Upstream returned {r.status_code}")
        total = 0
        chunks = []
        limit = int(MAX_MB * 1024 * 1024)
        for chunk in r.iter_content(chunk_size=1048576):  # 1MB
            if chunk:
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, detail=f"PDF too large (> {MAX_MB} MB)")
                chunks.append(chunk)
        return b"".join(chunks)

@app.post("/v1/encrypted")
def pdf_to_text_encrypted(payload: EncryptedPayload, request: Request):
    """
    Reçoit un JSON chiffré :
      { "url": "<signed-hubspot-url>", "ocr": false }
    Retourne un JSON chiffré :
      { "text": "...", "used_ocr": false, "bytes": 12345, "ms": 231 }
    """
    t0 = time.time()
    try:
        req_obj = decrypt_json(payload.cipher, SHARED_KEY_B64)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    url = req_obj.get("url")
    if not url or not isinstance(url, str):
        raise HTTPException(400, detail="Missing 'url'")

    _validate_url(url)

    pdf_bytes = _fetch_pdf(url)
    text, used_ocr = pdf_to_text_bytes(pdf_bytes)

    resp_obj: Dict[str, Any] = {
        "text": text,
        "used_ocr": bool(used_ocr),
        "bytes": len(pdf_bytes),
        "ms": int((time.time() - t0) * 1000),
    }
    cipher_resp = encrypt_json(resp_obj, SHARED_KEY_B64)
    return {"cipher": cipher_resp}

@app.get("/healthz")
def healthz():
    return {"ok": True}
