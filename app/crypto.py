import base64
from typing import Dict, Any
from nacl import utils
from nacl.secret import SecretBox
from nacl.exceptions import CryptoError
import json

NONCE_LEN = 24  # XChaCha20-Poly1305

def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("utf-8"))

def encrypt_json(obj: Dict[str, Any], key_b64: str) -> str:
    key = b64d(key_b64)
    box = SecretBox(key)
    nonce = utils.random(NONCE_LEN)
    plaintext = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    ct = box.encrypt(plaintext, nonce)
    return b64e(ct)  # nonce + ciphertext + mac

def decrypt_json(cipher_b64: str, key_b64: str) -> Dict[str, Any]:
    key = b64d(key_b64)
    box = SecretBox(key)
    try:
        pt = box.decrypt(b64d(cipher_b64))
    except CryptoError as e:
        raise ValueError(f"Decryption failed: {e}")
    return json.loads(pt.decode("utf-8"))
