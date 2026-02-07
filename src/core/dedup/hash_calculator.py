"""
Image Hash Calculator
====================

Provides perceptual and cryptographic hash calculation for images.
Supports pHash, dHash, aHash, wHash for perceptual hashing and
MD5, SHA1, SHA256, SHA512 for cryptographic hashing.

Adapted from: https://github.com/deanable/python-dedupe
"""

import hashlib
import base64
import io
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union
from pathlib import Path

from PIL import Image
import imagehash


@dataclass
class HashResult:
    """
    Dataclass to store the result of a hash calculation.
    """
    hash_value: str
    algorithm: str
    timestamp: float
    bit_length: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImageHashCalculator:
    """
    Class to calculate perceptual and cryptographic hashes for images.
    """

    SUPPORTED_PERCEPTUAL_ALGOS = {
        'phash': imagehash.phash,
        'dhash': imagehash.dhash,
        'ahash': imagehash.average_hash,
        'whash': imagehash.whash
    }

    SUPPORTED_CRYPTO_ALGOS = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha256': hashlib.sha256,
        'sha512': hashlib.sha512
    }

    def load_image_from_base64(self, b64_string: str) -> Image.Image:
        """
        Loads an image from a base64 string.
        Strips data URI prefix if present.
        """
        if ',' in b64_string:
            b64_string = b64_string.split(',', 1)[1]

        try:
            image_data = base64.b64decode(b64_string)
            return self.load_image_from_bytes(image_data)
        except Exception as e:
            raise ValueError(f"Failed to load image from base64: {e}")

    def load_image_from_bytes(self, binary_data: bytes) -> Image.Image:
        """
        Loads an image from bytes.
        """
        try:
            image = Image.open(io.BytesIO(binary_data))
            # Convert to RGB to ensure consistency for perceptual hashing
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return image
        except Exception as e:
            raise ValueError(f"Failed to load image from bytes: {e}")

    def load_image_from_path(self, file_path: Union[str, Path]) -> Image.Image:
        """
        Loads an image from a file path.
        """
        try:
            with open(file_path, 'rb') as f:
                return self.load_image_from_bytes(f.read())
        except Exception as e:
            raise ValueError(f"Failed to load image from path {file_path}: {e}")

    def calculate_perceptual_hash(self, image: Image.Image, algorithm: str = 'phash') -> HashResult:
        """
        Calculates a perceptual hash for the given image.
        """
        algo_name = algorithm.lower()
        if algo_name not in self.SUPPORTED_PERCEPTUAL_ALGOS:
            raise ValueError(f"Unsupported perceptual algorithm: {algorithm}")

        hash_func = self.SUPPORTED_PERCEPTUAL_ALGOS[algo_name]
        try:
            # imagehash functions return an ImageHash object
            hash_obj = hash_func(image)
            hash_str = str(hash_obj)
            # imagehash objects usually have a hash array. typical length is 64 bits (8 bytes) -> 16 hex chars
            # hash_obj.hash is a numpy array of bools.
            # bit_length is hash_obj.hash.size
            bit_length = hash_obj.hash.size

            return HashResult(
                hash_value=hash_str,
                algorithm=algo_name,
                timestamp=time.time(),
                bit_length=bit_length,
                metadata={'original_size': image.size}
            )
        except Exception as e:
            raise RuntimeError(f"Error calculating {algorithm}: {e}")

    def calculate_cryptographic_hash(self, image_bytes: bytes, algorithm: str = 'sha256') -> HashResult:
        """
        Calculates a cryptographic hash for the given image bytes.
        """
        algo_name = algorithm.lower()
        if algo_name not in self.SUPPORTED_CRYPTO_ALGOS:
            raise ValueError(f"Unsupported cryptographic algorithm: {algorithm}")

        hash_func = self.SUPPORTED_CRYPTO_ALGOS[algo_name]
        try:
            hasher = hash_func()
            hasher.update(image_bytes)
            hash_hex = hasher.hexdigest()
            # bit_length = digest_size * 8
            bit_length = hasher.digest_size * 8

            return HashResult(
                hash_value=hash_hex,
                algorithm=algo_name,
                timestamp=time.time(),
                bit_length=bit_length,
                metadata={'byte_size': len(image_bytes)}
            )
        except Exception as e:
            raise RuntimeError(f"Error calculating {algorithm}: {e}")

    def calculate_all_hashes(self, image: Image.Image, image_bytes: Optional[bytes] = None) -> Dict[str, HashResult]:
        """
        Calculates all supported hashes (perceptual and cryptographic).
        If image_bytes is not provided, cryptographic hashes will be skipped.

        Returns a dictionary mapping algorithm name to HashResult.
        """
        results = {}

        # Perceptual hashes
        for algo in self.SUPPORTED_PERCEPTUAL_ALGOS:
            try:
                results[algo] = self.calculate_perceptual_hash(image, algorithm=algo)
            except Exception:
                pass

        # Cryptographic hashes
        if image_bytes:
            for algo in self.SUPPORTED_CRYPTO_ALGOS:
                try:
                    results[algo] = self.calculate_cryptographic_hash(image_bytes, algorithm=algo)
                except Exception:
                    pass

        return results
