"""Diagnose why Lattice ratios are poor for text/code single files."""
import os, sys, struct, io
sys.path.insert(0, ".")
import lattice_archive

# Check static dict size
dict_size = len(lattice_archive.STATIC_DICT) if hasattr(lattice_archive, 'STATIC_DICT') else 0
print(f"Static dict size: {dict_size:,} bytes")

# Check what happens when we compress pride.txt
src = "local_dataset/pride.txt"
data = open(src, "rb").read()
print(f"\nOriginal: {len(data):,} bytes")

# Compress and inspect archive
archive = "scratch/diag_test.lat"
mode, orig, nf = lattice_archive.LatticeArchiveEngine.compress(
    "local_dataset", archive, virtually_lossless=0, solid=True
)
arch_size = os.path.getsize(archive)
print(f"Lattice archive (whole local_dataset): {arch_size:,} bytes")
print(f"Mode: {mode}")

# Now compress just pride.txt alone
import tempfile, shutil
tmp = tempfile.mkdtemp()
src_dir = os.path.join(tmp, "src")
os.makedirs(src_dir)
shutil.copy("local_dataset/pride.txt", src_dir)
mode2, orig2, nf2 = lattice_archive.LatticeArchiveEngine.compress(
    src_dir, os.path.join(tmp, "pride.lat"), virtually_lossless=0, solid=True
)
pride_arch = os.path.getsize(os.path.join(tmp, "pride.lat"))
print(f"\nPride.txt alone:")
print(f"  Original: {orig2:,} bytes")
print(f"  Archive: {pride_arch:,} bytes (ratio: {orig2/pride_arch:.2f}x)")
print(f"  Mode: {mode2}")

# Break down the archive to see overhead
with open(os.path.join(tmp, "pride.lat"), "rb") as f:
    raw = f.read()
print(f"  Total archive bytes: {len(raw)}")
print(f"  Magic: {raw[:4]}")
print(f"  Version: {raw[4]}")
# Parse varint for num_files
pos = 5
val = 0; shift = 0
while pos < len(raw):
    b = raw[pos]; pos += 1
    val |= (b & 0x7F) << shift
    shift += 7
    if not (b & 0x80): break
print(f"  num_files: {val}")
# mode byte
print(f"  mode: {raw[pos]}"); pos += 1
# dict_size varint
val2 = 0; shift = 0
while pos < len(raw):
    b = raw[pos]; pos += 1
    val2 |= (b & 0x7F) << shift
    shift += 7
    if not (b & 0x80): break
print(f"  dict_size: {val2:,} bytes")
print(f"  CRC footer: {raw[-8:-4]} + {raw[-4:].hex()}")
print(f"  Compressed data: {len(raw) - pos - 8:,} bytes (after header, before CRC)")
overhead = pos + 8 + val2  # header + CRC + dict
print(f"  Total overhead (header + dict + CRC): {overhead:,} bytes")

# Now test: what if we just compress with zstd directly (no archive)?
import zstandard as zstd_mod
cctx = zstd_mod.ZstdCompressor(level=9)
zstd_direct = cctx.compress(data)
print(f"\n  Zstd-9 direct on pride.txt: {len(zstd_direct):,} bytes (ratio: {len(data)/len(zstd_direct):.2f}x)")

# Check if word tokenization is expanding or shrinking
# The tokenize_words function
if hasattr(lattice_archive, 'tokenize_words'):
    tok = lattice_archive.tokenize_words(data)
    if tok:
        tok_data = b"L_WT" + tok
        print(f"  Word-tokenized size: {len(tok_data):,} bytes (vs {len(data):,} original)")
        zstd_tok = cctx.compress(tok_data)
        print(f"  Zstd-9 on tokenized: {len(zstd_tok):,} bytes (ratio: {len(data)/len(zstd_tok):.2f}x)")
    else:
        print(f"  Word tokenization returned None")

# Check with static dict
dict_data = lattice_archive.STATIC_DICT if hasattr(lattice_archive, 'STATIC_DICT') else b""
if dict_data:
    zdict = zstd_mod.ZstdCompressionDict(dict_data)
    cctx_dict = zstd_mod.ZstdCompressor(level=9, dict_data=zdict)
    zstd_dict = cctx_dict.compress(data)
    print(f"  Zstd-9 + static dict: {len(zstd_dict):,} bytes (ratio: {len(data)/len(zstd_dict):.2f}x)")

shutil.rmtree(tmp, ignore_errors=True)
os.remove(archive)
