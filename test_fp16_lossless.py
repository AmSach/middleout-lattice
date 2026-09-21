"""
Benchmarks lossless compression of Float16 model weights.
"""
import os
import numpy as np
import torch
import torch.nn as nn
import zstandard as zstd
import brotli
import lattice_archive as la

def get_real_weights_fp16():
    model = nn.Sequential(
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, 256),
        nn.ReLU(),
        nn.Linear(256, 256)
    )
    weights = []
    for p in model.parameters():
        weights.append(p.detach().cpu().numpy().flatten().astype(np.float16))
    return np.concatenate(weights)

def main():
    weights_fp16 = get_real_weights_fp16()
    orig_bytes = weights_fp16.tobytes()
    orig_size = len(orig_bytes)
    
    print(f"Original FP16 weights size: {orig_size:,} bytes")
    
    # Save raw FP16 weights
    os.makedirs("fp16_test", exist_ok=True)
    raw_path = "fp16_test/raw.bin"
    with open(raw_path, "wb") as f:
        f.write(orig_bytes)
        
    # Compress with Lattice (Strict Lossless)
    archive_path = "fp16_test/archive.lattice"
    la.LatticeArchiveEngine.compress(raw_path, archive_path, virtually_lossless=0, solid=True)
    
    comp_size = os.path.getsize(archive_path)
    ratio = orig_size / comp_size
    print(f"Lattice Lossless FP16 Compression: {comp_size:,} B (ratio={ratio:.3f}x)")
    
    # Clean up
    import shutil
    shutil.rmtree("fp16_test", ignore_errors=True)

if __name__ == "__main__":
    main()
