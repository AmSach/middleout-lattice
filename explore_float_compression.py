"""
Benchmarks different compressors (Zstd, Brotli, LZMA) on transposed float32 weights.
"""
import numpy as np
import zstandard as zstd
import brotli
import lzma

def gen_float32_weights(size_kb=1024):
    n_floats = (size_kb * 1024) // 4
    np.random.seed(42)
    weights = np.concatenate([
        np.random.normal(0, 0.02, n_floats // 4).astype(np.float32),
        np.random.normal(0, 0.1, n_floats // 4).astype(np.float32),
        np.ones(n_floats // 8, dtype=np.float32),
        np.zeros(n_floats // 8, dtype=np.float32),
        np.random.uniform(-1, 1, n_floats // 4).astype(np.float32),
    ])
    return weights.tobytes()

def transpose_bytes(data, elem_size):
    n = len(data)
    padded = data + b'\x00' * ((elem_size - (n % elem_size)) % elem_size)
    num_elems = len(padded) // elem_size
    transposed = bytearray(len(padded))
    for col in range(elem_size):
        for i in range(num_elems):
            transposed[col * num_elems + i] = padded[i * elem_size + col]
    return bytes(transposed), num_elems

def run_experiment():
    raw_data = gen_float32_weights(1024)
    orig_size = len(raw_data)
    trans, num_elems = transpose_bytes(raw_data, 4)

    print(f"Original: {orig_size:,} bytes\n")

    # Baselines (No Transpose)
    z_base = len(zstd.ZstdCompressor(level=22).compress(raw_data))
    b_base = len(brotli.compress(raw_data, quality=11))
    l_base = len(lzma.compress(raw_data, preset=9))
    print(f"Baselines (No Transpose):")
    print(f"  Zstd-22: {z_base:,} B (ratio={orig_size/z_base:.3f}x)")
    print(f"  Brotli-11: {b_base:,} B (ratio={orig_size/b_base:.3f}x)")
    print(f"  LZMA-9: {l_base:,} B (ratio={orig_size/l_base:.3f}x)")
    print()

    # Transposed Compressions
    z_trans = len(zstd.ZstdCompressor(level=22).compress(trans))
    b_trans = len(brotli.compress(trans, quality=11))
    l_trans = len(lzma.compress(trans, preset=9))
    print(f"Transposed Compressions:")
    print(f"  Transpose + Zstd-22: {z_trans:,} B (ratio={orig_size/z_trans:.3f}x)")
    print(f"  Transpose + Brotli-11: {b_trans:,} B (ratio={orig_size/b_trans:.3f}x)")
    print(f"  Transpose + LZMA-9: {l_trans:,} B (ratio={orig_size/l_trans:.3f}x)")

if __name__ == "__main__":
    run_experiment()
