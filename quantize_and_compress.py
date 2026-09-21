"""
Demonstration of combining Quantization (INT8/INT4) and custom bit-masking
with Lattice compression to achieve massive, state-of-the-art model weight compression.
"""
import os
import shutil
import numpy as np
import torch
import torch.nn as nn
import lattice_archive as la

def quantize_int8(tensor):
    min_val = tensor.min()
    max_val = tensor.max()
    if min_val == max_val:
        return np.zeros_like(tensor, dtype=np.uint8), 1.0, 0.0
    
    scale = (max_val - min_val) / 255.0
    zero_point = -min_val / scale
    q_tensor = np.clip(np.round(tensor / scale + zero_point), 0, 255).astype(np.uint8)
    return q_tensor, scale, zero_point

def dequantize_int8(q_tensor, scale, zero_point):
    return (q_tensor.astype(np.float32) - zero_point) * scale

def quantize_int4(tensor):
    min_val = tensor.min()
    max_val = tensor.max()
    if min_val == max_val:
        return np.zeros(len(tensor) // 2, dtype=np.uint8), 1.0, 0.0
    
    scale = (max_val - min_val) / 15.0
    zero_point = -min_val / scale
    q_vals = np.clip(np.round(tensor / scale + zero_point), 0, 15).astype(np.uint8)
    
    if len(q_vals) % 2 != 0:
        q_vals = np.append(q_vals, 0)
    packed = (q_vals[0::2] << 4) | q_vals[1::2]
    return packed, scale, zero_point

def dequantize_int4(packed, scale, zero_point):
    q_vals = np.zeros(len(packed) * 2, dtype=np.uint8)
    q_vals[0::2] = (packed >> 4) & 0x0F
    q_vals[1::2] = packed & 0x0F
    return (q_vals.astype(np.float32) - zero_point) * scale

def main():
    np.random.seed(42)
    weights = np.random.normal(0, 0.05, size=1024 * 1024).astype(np.float32)
    
    os.makedirs("quant_tensors", exist_ok=True)
    raw_path = "quant_tensors/raw_weights.bin"
    with open(raw_path, "wb") as f:
        f.write(weights.tobytes())
        
    orig_size = os.path.getsize(raw_path)
    print(f"Original Model Weight Size: {orig_size / (1024*1024):.2f} MB ({orig_size:,} bytes)")
    print("=" * 80)
    
    # --- Strategies ---
    def run_strategy(label, lvl=0, qmode=None):
        archive_path = f"quant_tensors/strat_{lvl}_{qmode}.lattice"
        if os.path.exists(archive_path):
            os.remove(archive_path)
            
        if qmode == "int8":
            q_int8, scale8, zp8 = quantize_int8(weights)
            payload_path = "quant_tensors/temp_payload.bin"
            with open(payload_path, "wb") as f:
                f.write(q_int8.tobytes())
            la.LatticeArchiveEngine.compress(payload_path, archive_path, virtually_lossless=0, solid=True)
            mse = np.mean((weights - dequantize_int8(q_int8, scale8, zp8)) ** 2)
        elif qmode == "int4":
            q_int4, scale4, zp4 = quantize_int4(weights)
            payload_path = "quant_tensors/temp_payload.bin"
            with open(payload_path, "wb") as f:
                f.write(q_int4.tobytes())
            la.LatticeArchiveEngine.compress(payload_path, archive_path, virtually_lossless=0, solid=True)
            mse = np.mean((weights - dequantize_int4(q_int4, scale4, zp4)) ** 2)
        else:
            la.LatticeArchiveEngine.compress(raw_path, archive_path, virtually_lossless=lvl, solid=True)
            # Calculate MSE manually for bitmask
            u32 = weights.view(np.uint32)
            bits_to_mask = lvl
            if lvl == 1: bits_to_mask = 8
            elif lvl == 2: bits_to_mask = 16
            elif lvl == 3: bits_to_mask = 23
            
            mask = np.uint32((0xFFFFFFFF << bits_to_mask) & 0xFFFFFFFF)
            masked_floats = (u32 & mask).view(np.float32)
            mse = np.mean((weights - masked_floats) ** 2)
            
        comp_size = os.path.getsize(archive_path)
        ratio = orig_size / comp_size
        saved = (1.0 - (comp_size / orig_size)) * 100
        err_str = f"{mse:.2e}" if mse > 0 else "0.00"
        print(f"{label:<38} | {comp_size:>9,} B  | {ratio:>8.2f}x  | {saved:>10.1f}%  | {err_str}")

    print(f"{'Method / Strategy':<38} | {'Size':<12} | {'Ratio':<10} | {'Space Saved':<12} | {'MSE Error'}")
    print("-" * 90)
    
    print(f"{'Original FP32 Weights':<38} | {orig_size:>9,} B  | {1.0:>8.2f}x  | {0.0:>10.1f}%  | 0.00")
    run_strategy("Strict Lossless Lattice", lvl=0)
    run_strategy("Mask Preset 1 (8-bit)", lvl=1)
    run_strategy("Mask Preset 2 (16-bit)", lvl=2)
    run_strategy("Custom Mask 18-bit (Level 18)", lvl=18)
    run_strategy("Custom Mask 20-bit (Level 20)", lvl=20)
    run_strategy("Custom Mask 22-bit (Level 22)", lvl=22)
    run_strategy("Mask Preset 3 (23-bit)", lvl=3)
    run_strategy("INT8 Quantization + Lattice", qmode="int8")
    run_strategy("INT4 Quantization + Lattice", qmode="int4")
    
    # Cleanup
    shutil.rmtree("quant_tensors", ignore_errors=True)

if __name__ == "__main__":
    main()
