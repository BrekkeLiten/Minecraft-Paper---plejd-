"""Plejd mesh crypto, as published for the local Bluetooth protocol.

The payload cipher is AES-128-ECB used as a keystream:

    seed      = address || address || address[:4]
    keystream = AES-128-ECB(key, seed)
    out[i]    = data[i] XOR keystream[i % 16]

``address`` is the 6-byte value from the connected node's AccessAddress
characteristic (the BLE MAC reversed). ``key`` is the 16-byte site crypto key.

Login folds SHA-256(challenge XOR key) from 32 bytes down to 16 by XORing
the two halves.
"""

from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def parse_key(text: str) -> bytes:
    cleaned = "".join(text.split()).replace("-", "")
    if len(cleaned) != 32 or any(char not in "0123456789abcdefABCDEF" for char in cleaned):
        raise ValueError("Plejd crypto key must be 32 hex characters (16 bytes)")
    return bytes.fromhex(cleaned)


def mesh_crypt(key: bytes, address: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("site key must be 16 bytes")
    if len(address) != 6:
        raise ValueError("cipher address must be 6 bytes")
    seed = address + address + address[:4]
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    stream = encryptor.update(seed) + encryptor.finalize()
    return bytes(byte ^ stream[index % 16] for index, byte in enumerate(data))


def auth_response(key: bytes, challenge: bytes) -> bytes:
    if len(key) != len(challenge):
        raise ValueError("key and challenge must be the same length")
    if len(key) not in (16, 32):
        raise ValueError("key must be 16 or 32 bytes")
    mixed = int.from_bytes(key, "big") ^ int.from_bytes(challenge, "big")
    digest = hashlib.sha256(mixed.to_bytes(len(key), "big")).digest()
    return bytes(left ^ right for left, right in zip(digest[:16], digest[16:], strict=True))
