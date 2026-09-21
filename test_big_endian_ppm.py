"""
Tests the compression of big-endian float32 layouts ([b3, b2, b1, b0])
against standard little-endian and transposed layouts.
"""
import os
import numpy as np
import torch
import torch.nn as nn
import zstandard as zstd
import brotli
import lzma

def get_real_weights():
    model = nn.Sequential(
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, 256)
    )
    weights = []
    for p in model.parameters():
        weights.append(p.detach().cpu().numpy().flatten().astype(np.float32))
    return np.concatenate(weights)

def transpose_bytes(data, elem_size):
    n = len(data)
    padded = data + b'\x00' * ((elem_size - (n % elem_size)) % elem_size)
    num_elems = len(padded) // elem_size
    transposed = bytearray(len(padded))
    for col in range(elem_size):
        for i in range(num_elems):
            transposed[col * num_elems + i] = padded[i * elem_size + col]
    return bytes(transposed)

def main():
    weights = get_real_weights()
    orig_bytes = weights.tobytes()
    orig_size = len(orig_bytes)
    
    print(f"Original weights size: {orig_size / (1024*1024):.2f} MB ({orig_size:,} bytes)")
    print("-" * 60)
    
    # 1. Little Endian (raw)
    z_le = len(zstd.ZstdCompressor(level=22).compress(orig_bytes))
    b_le = len(brotli.compress(orig_bytes, quality=11))
    l_le = len(lzma.compress(orig_bytes, preset=9))
    
    # 2. Transposed
    trans = transpose_bytes(orig_bytes, 4)
    z_tr = len(zstd.ZstdCompressor(level=22).compress(trans))
    b_tr = len(brotli.compress(trans, quality=11))
    l_tr = len(lzma.compress(trans, preset=9))
    
    # 3. Big Endian (byte swapped [b3, b2, b1, b0])
    # In float32 np.ndarray, we can convert to big endian:
    weights_be = weights.byteswap().tobytes()
    z_be = len(zstd.ZstdCompressor(level=22).compress(weights_be))
    b_be = len(brotli.compress(weights_be, quality=11))
    l_be = len(lzma.compress(weights_be, preset=9))
    
    # Print comparison
    print(f"{'Layout & Compressor':<30} | {'Size':<12} | {'Ratio':<10}")
    print("-" * 60)
    print(f"Raw LE + Zstd-22               | {z_le:>9,} B  | {orig_size/z_le:>8.3f}x")
    print(f"Raw LE + Brotli-11             | {b_le:>9,} B  | {orig_size/b_le:>8.3f}x")
    print(f"Raw LE + LZMA-9                | {l_le:>9,} B  | {orig_size/l_le:>8.3f}x")
    print("-" * 60)
    print(f"Transposed + Zstd-22           | {z_tr:>9,} B  | {orig_size/z_tr:>8.3f}x")
    print(f"Transposed + Brotli-11         | {b_tr:>9,} B  | {orig_size/b_tr:>8.3f}x")
    print(f"Transposed + LZMA-9            | {l_tr:>9,} B  | {orig_size/l_tr:>8.3f}x")
    print("-" * 60)
    print(f"Big-Endian + Zstd-22           | {z_be:>9,} B  | {orig_size/z_be:>8.3f}x")
    print(f"Big-Endian + Brotli-11         | {b_be:>9,} B  | {orig_size/b_be:>8.3f}x")
    print(f"Big-Endian + LZMA-9            | {l_be:>9,} B  | {orig_size/l_be:>8.3f}x")

if __name__ == "__main__":
    main()
