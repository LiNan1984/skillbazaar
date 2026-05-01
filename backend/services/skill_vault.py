from __future__ import annotations

import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

_MASTER_KEY = os.environ.get(
    "SKILLBAZAAR_MASTER_KEY",
    "skillbazaar-default-master-key-change-in-production-2026"
)


def _derive_key(master_key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(master_key.encode())


def encrypt_content(plaintext: bytes, master_key: str = _MASTER_KEY) -> dict:
    salt = os.urandom(16)
    key = _derive_key(master_key, salt)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext, None)
    return {
        "encrypted_blob": ciphertext,
        "encryption_iv": iv.hex(),
        "encryption_salt": salt.hex(),
        "content_hash": hashlib.sha256(plaintext).hexdigest(),
        "file_size": len(plaintext),
    }


def decrypt_content(
    encrypted_blob: bytes,
    iv_hex: str,
    salt_hex: str,
    master_key: str = _MASTER_KEY,
) -> bytes:
    salt = bytes.fromhex(salt_hex)
    iv = bytes.fromhex(iv_hex)
    key = _derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, encrypted_blob, None)


def verify_integrity(plaintext: bytes, expected_hash: str) -> bool:
    actual_hash = hashlib.sha256(plaintext).hexdigest()
    return actual_hash == expected_hash
