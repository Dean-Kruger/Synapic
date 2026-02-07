"""
Hash Comparison Utilities
=========================

Functions for comparing image hashes using Hamming distance
and calculating similarity percentages.

Adapted from: https://github.com/deanable/python-dedupe
"""


def calculate_hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculates the Hamming distance between two hex strings.
    Raises ValueError if lengths differ.
    """
    if len(hash1) != len(hash2):
        raise ValueError("Hashes must be of the same length to calculate Hamming distance.")

    # Convert hex to integers
    try:
        int1 = int(hash1, 16)
        int2 = int(hash2, 16)
    except ValueError:
        raise ValueError("Invalid hex string provided.")

    # XOR and count set bits
    xor_result = int1 ^ int2
    return bin(xor_result).count('1')


def calculate_similarity_percentage(hamming_distance: int, hash_bit_length: int) -> float:
    """
    Calculates similarity percentage based on Hamming distance and total bit length.
    Formula: (1 - distance / bit_length) * 100
    """
    if hash_bit_length <= 0:
        raise ValueError("Bit length must be positive.")
    if hamming_distance < 0:
        raise ValueError("Hamming distance cannot be negative.")

    similarity = (1 - hamming_distance / hash_bit_length) * 100.0
    return max(0.0, min(100.0, similarity))


def are_hashes_similar(hash1: str, hash2: str, threshold: float = 95.0) -> bool:
    """
    Checks if two hashes are similar based on the threshold.
    Similarity is calculated using Hamming distance.
    """
    if len(hash1) != len(hash2):
        return False

    try:
        # Calculate bit length from hex string length (1 hex char = 4 bits)
        bit_length = len(hash1) * 4
        distance = calculate_hamming_distance(hash1, hash2)
        similarity = calculate_similarity_percentage(distance, bit_length)
        return similarity >= threshold
    except ValueError:
        return False


def are_hashes_exact_match(hash1: str, hash2: str) -> bool:
    """
    Checks if two hashes are identical.
    """
    return hash1 == hash2
