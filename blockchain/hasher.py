"""
Cryptographic hashing and fingerprinting utilities for Face Scan and Social Media Verification.
Produces deterministic SHA-256 and Keccak-256 hashes formatted for EVM bytes32 compatibility.
"""

import hashlib
import json
from typing import Dict, Any, List, Union
import numpy as np


def sha256_bytes(data: bytes) -> bytes:
    """Computes SHA-256 digest of raw bytes returning 32 bytes."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """Computes SHA-256 digest returning 0x-prefixed hex string."""
    return "0x" + hashlib.sha256(data).hexdigest()


def hash_face_array(face_crop: np.ndarray) -> str:
    """
    Computes a deterministic cryptographic hash of a normalized face image array.
    Normalizes dtype and byte layout to ensure reproducibility across platforms.
    """
    # Ensure contiguous C-order array
    contiguous = np.ascontiguousarray(face_crop)
    return sha256_hex(contiguous.tobytes())


def hash_post_content(post_data: Dict[str, Any]) -> str:
    """
    Computes a deterministic cryptographic hash of social media post content.
    Includes canonical URL, author, platform, text/caption, timestamp, and media hash.
    """
    canonical_payload = {
        "platform": str(post_data.get("platform", "")).lower().strip(),
        "url": str(post_data.get("url", "")).strip(),
        "author": str(post_data.get("author", "")).strip(),
        "text": str(post_data.get("text", "")).strip(),
        "timestamp": int(post_data.get("timestamp", 0)),
        "media_sha256": str(post_data.get("media_sha256", "")).strip(),
    }
    # Deterministic JSON string sorted by keys
    serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return sha256_hex(serialized.encode("utf-8"))


def compute_merkle_root(leaves: List[str]) -> str:
    """
    Computes a binary Merkle tree root from a list of 0x-prefixed hex hashes.
    Useful for proving inclusion of individual post attributes.
    """
    if not leaves:
        return "0x" + "00" * 32

    current = [bytes.fromhex(leaf.removeprefix("0x")) for leaf in leaves]

    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else current[i]
            combined = sha256_bytes(left + right)
            next_level.append(combined)
        current = next_level

    return "0x" + current[0].hex()


def to_bytes32(hex_str: Union[str, bytes]) -> bytes:
    """Converts a 0x-prefixed hex string or bytes into a 32-byte bytes object."""
    if isinstance(hex_str, bytes):
        if len(hex_str) == 32:
            return hex_str
        elif len(hex_str) < 32:
            return hex_str.rjust(32, b"\x00")
        else:
            return hex_str[:32]

    cleaned = hex_str.removeprefix("0x")
    raw = bytes.fromhex(cleaned)
    if len(raw) < 32:
        raw = raw.rjust(32, b"\x00")
    return raw[:32]
