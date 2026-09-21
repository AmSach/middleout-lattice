"""
Benchmarks float-to-ordinal mapping and ordinal delta encoding for lossless compression.
"""
import numpy as np
import torch
import torch.nn as nn
import zstandard as zstd

def get_real_weights():
    model = nn.Sequential(
        nn.Linear(512, 512),
        nn.ReLU(),
        nn.Linear(512, 512),
        nn.ReLU(),
        nn.Linear(512, 512)
    )
    weights = []
    for p in model.parameters():
        weights.append(p.detach().cpu().numpy().flatten().astype(np.float32))
    return np.concatenate(weights)

def float_to_ordinals(f_arr):
    # Interpret float32 as uint32
    u = f_arr.view(np.uint32)
    # Get sign bit
    sign = (u & 0x80000000) != 0
    # Map negative float32 values so they are ordered, and positive values so they are ordered.
    # IEEE 754 negative floats have the sign bit set, and the rest is the magnitude.
    # To make them monotonic:
    # Negative floats: 0x80000000 - u (maps large negative to smaller integer)
    # Positive floats: u (positive floats already increase monotonically with u)
    ordinals = np.where(sign, 0x80000000 - u, u)
    # Cast to signed 32-bit integers
    return ordinals.astype(np.int32)

def ordinals_to_floats(ord_arr):
    u = np.where(ord_arr < 0, 0x80000000 - ord_arr.astype(np.uint32), ord_arr.astype(np.uint32))
    return u.view(np.float32)

def transpose_bytes_reversed(data, elem_size):
    n = len(data)
    padded = data + b'\x00' * ((elem_size - (n % elem_size)) % elem_size)
    num_elems = len(padded) // elem_size
    transposed = bytearray(len(padded))
    for col in range(elem_size):
        dest_col = elem_size - 1 - col
        for i in range(num_elems):
            transposed[dest_col * num_elems + i] = padded[i * elem_size + col]
    return bytes(transposed)

def main():
    weights = get_real_weights()
    orig_bytes = weights.tobytes()
    orig_size = len(orig_bytes)
    
    print(f"Original weights size: {orig_size:,} bytes")
    
    # 1. Baseline: Float32 Transposed (Reversed, No Delta)
    trans_base = transpose_bytes_reversed(orig_bytes, 4)
    z_base = len(zstd.ZstdCompressor(level=22).compress(trans_base))
    print(f"1. Baseline Float32 Transpose: {z_base:,} B (ratio={orig_size/z_base:.4f}x)")
    
    # 2. Ordinal Transposed (No Delta)
    ordinals = float_to_ordinals(weights)
    # Verify lossless reconstruction of ordinals
    reconstructed_floats = ordinals_to_floats(ordinals)
    assert np.all(weights == reconstructed_floats), "Ordinal mapping is not lossless!"
    
    ord_bytes = ordinals.tobytes()
    trans_ord = transpose_bytes_reversed(ord_bytes, 4)
    z_ord = len(zstd.ZstdCompressor(level=22).compress(trans_ord))
    print(f"2. Ordinal Transpose: {z_ord:,} B (ratio={orig_size/z_ord:.4f}x)")
    
    # 3. Ordinal 32-bit Integer Delta + Transposed
    ord_delta = np.zeros_like(ordinals)
    ord_delta[0] = ordinals[0]
    ord_delta[1:] = ordinals[1:] - ordinals[:-1]
    
    trans_ord_delta = transpose_bytes_reversed(ord_delta.tobytes(), 4)
    z_ord_delta = len(zstd.ZstdCompressor(level=22).compress(trans_ord_delta))
    print(f"3. Ordinal 32-bit Delta + Transpose: {z_ord_delta:,} B (ratio={orig_size/z_ord_delta:.4f}x)")
    
if __name__ == "__main__":
    main()
