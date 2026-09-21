import numpy as np
import zstandard as zstd
import struct, random

random.seed(42)
floats = [random.gauss(0, 0.02) for _ in range(500000)]
data = bytearray()
for f in floats:
    data.extend(struct.pack("<f", f))
raw_bytes = bytes(data)

orig_len = len(raw_bytes)
print(f"Original float array: {orig_len:,} bytes ({orig_len/1024/1024:.2f} MB)")

# Baseline Zstd-22
z22 = zstd.ZstdCompressor(level=22).compress(raw_bytes)
print(f"Zstd-22 baseline: {len(z22):,} bytes ({orig_len/len(z22):.2f}x)")

# Method 1: Pure Column Transpose (4-byte element size)
arr_u8 = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(-1, 4)
transposed = arr_u8.T.tobytes()
z22_trans = zstd.ZstdCompressor(level=22).compress(transposed)
print(f"Column Transpose + Zstd-22: {len(z22_trans):,} bytes ({orig_len/len(z22_trans):.2f}x)")

# Method 2: Bit-XOR Delta + Column Transpose
arr_u32 = np.frombuffer(raw_bytes, dtype=np.uint32).copy()
xor_delta = np.empty_like(arr_u32)
xor_delta[0] = arr_u32[0]
np.bitwise_xor(arr_u32[1:], arr_u32[:-1], out=xor_delta[1:])

xor_u8 = xor_delta.view(np.uint8).reshape(-1, 4)
xor_transposed = xor_u8.T.tobytes()
z22_xor_trans = zstd.ZstdCompressor(level=22).compress(xor_transposed)
print(f"Bit-XOR Delta + Transpose + Zstd-22: {len(z22_xor_trans):,} bytes ({orig_len/len(z22_xor_trans):.2f}x)")

# Method 3: Arithmetic 32-bit Delta + Column Transpose
diff_u32 = np.empty_like(arr_u32)
diff_u32[0] = arr_u32[0]
diff_u32[1:] = arr_u32[1:] - arr_u32[:-1]
diff_trans = diff_u32.view(np.uint8).reshape(-1, 4).T.tobytes()
z22_diff_trans = zstd.ZstdCompressor(level=22).compress(diff_trans)
print(f"Arithmetic Delta + Transpose + Zstd-22: {len(z22_diff_trans):,} bytes ({orig_len/len(z22_diff_trans):.2f}x)")
