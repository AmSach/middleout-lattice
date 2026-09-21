"""
Middleout-Lattice Comprehensive Benchmark Suite
Tests compression ratio, speed, and losslessness across diverse file types.
Compares against Brotli Max (quality=11) and Zstd Max (level=22).
"""
import os, sys, time, json, hashlib, struct, tempfile, shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zstandard as zstd
import brotli
import lattice_archive

# ============================================================================
# Test Data Generators
# ============================================================================

def gen_english_text(size_kb=64):
    """Generate realistic English prose."""
    paragraphs = [
        "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the English alphabet and has been used for centuries as a typing exercise. ",
        "Machine learning models have grown exponentially in size over the past decade. Modern large language models contain billions of parameters stored as floating point weights. ",
        "Compression algorithms work by finding and eliminating redundancy in data. Dictionary-based methods like LZ77 search for repeating byte sequences within a sliding window. ",
        "Neural networks learn representations of data through gradient descent optimization. Each layer transforms its input through a series of matrix multiplications and nonlinear activations. ",
        "The development of transformer architectures revolutionized natural language processing. Self-attention mechanisms allow models to capture long-range dependencies in sequential data. ",
        "Data compression is fundamentally limited by Shannon entropy, which measures the minimum number of bits required to encode a message without loss of information. ",
        "Floating point numbers follow the IEEE 754 standard, encoding values as a sign bit, exponent field, and mantissa field. The mantissa bits carry the precision of the number. ",
        "Efficient storage and transmission of AI models is critical for deployment at scale. Model checkpoints must be saved frequently during training to enable recovery from failures. ",
    ]
    text = ""
    while len(text) < size_kb * 1024:
        for p in paragraphs:
            text += p + "\n\n"
            if len(text) >= size_kb * 1024:
                break
    return text[:size_kb * 1024].encode("utf-8")

def gen_python_code(size_kb=32):
    """Generate realistic Python source code."""
    code = '''import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class TransformerBlock(nn.Module):
    """Multi-head self-attention transformer block."""
    def __init__(self, d_model=512, n_heads=8, d_ff=2048, dropout=0.1):
        super().__init__()
        self.attention = nn.MultiheadAttention(d_model, n_heads, dropout=dropout)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x, mask=None):
        attended = self.attention(x, x, x, attn_mask=mask)[0]
        x = self.norm1(x + attended)
        fed_forward = self.feed_forward(x)
        x = self.norm2(x + fed_forward)
        return x

class NeuralCompressor(nn.Module):
    """Neural network for byte-level compression."""
    def __init__(self, vocab_size=256, d_model=256, n_layers=6):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.positional = nn.Embedding(1024, d_model)
        self.blocks = nn.ModuleList([
            TransformerBlock(d_model) for _ in range(n_layers)
        ])
        self.output = nn.Linear(d_model, vocab_size)

    def forward(self, x):
        positions = torch.arange(x.size(1), device=x.device)
        x = self.embedding(x) + self.positional(positions)
        for block in self.blocks:
            x = block(x)
        return self.output(x)

def train_model(model, dataloader, epochs=10, lr=1e-4):
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)
    for epoch in range(epochs):
        total_loss = 0.0
        for batch_idx, (data, target) in enumerate(dataloader):
            optimizer.zero_grad()
            output = model(data)
            loss = F.cross_entropy(output.view(-1, 256), target.view(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()
        print(f"Epoch {epoch}: loss={total_loss:.4f}")

if __name__ == "__main__":
    model = NeuralCompressor()
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
'''
    result = code
    while len(result) < size_kb * 1024:
        result += "\n" + code
    return result[:size_kb * 1024].encode("utf-8")

def gen_json_data(size_kb=64):
    """Generate realistic JSON config/log data."""
    entries = []
    for i in range(size_kb * 8):
        entries.append({
            "id": i,
            "timestamp": f"2026-05-{(i%28)+1:02d}T{i%24:02d}:{i%60:02d}:00Z",
            "level": ["INFO", "WARNING", "ERROR", "DEBUG"][i % 4],
            "module": ["training", "inference", "data_loader", "optimizer"][i % 4],
            "message": f"Processing batch {i} with learning_rate=0.0001 and loss={np.random.uniform(0.1, 5.0):.6f}",
            "metrics": {
                "loss": round(np.random.uniform(0.01, 5.0), 6),
                "accuracy": round(np.random.uniform(0.5, 0.99), 4),
                "throughput_mbps": round(np.random.uniform(100, 2000), 2),
            }
        })
    data = json.dumps(entries, indent=2).encode("utf-8")
    return data[:size_kb * 1024] if len(data) > size_kb * 1024 else data

def gen_csv_data(size_kb=64):
    """Generate CSV tabular data."""
    header = "epoch,batch,loss,accuracy,lr,grad_norm,throughput,memory_mb\n"
    rows = header
    i = 0
    while len(rows) < size_kb * 1024:
        rows += f"{i//100},{i%100},{np.random.uniform(0.01,5):.6f},{np.random.uniform(0.5,0.99):.4f},0.0001,{np.random.uniform(0.1,10):.4f},{np.random.uniform(100,2000):.2f},{np.random.randint(1000,32000)}\n"
        i += 1
    return rows[:size_kb * 1024].encode("utf-8")

def gen_html_page(size_kb=32):
    """Generate HTML page."""
    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Lattice Compression Engine</title>
<style>
body { font-family: 'Inter', sans-serif; background: #0a0a1a; color: #e0e0ff; }
.container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
.card { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 2rem; margin: 1rem 0; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.stat-value { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; color: transparent; }
h1 { font-size: 3rem; background: linear-gradient(135deg, #6366f1, #ec4899); -webkit-background-clip: text; color: transparent; }
</style></head><body>
<div class="container">
<h1>Lattice Compression Engine</h1>
<div class="stats">
"""
    for i in range(size_kb * 4):
        html += f'<div class="card"><div class="stat-value">{np.random.uniform(1,100):.2f}x</div><p>Compression Ratio Test {i}</p></div>\n'
    html += "</div></div></body></html>"
    return html[:size_kb * 1024].encode("utf-8")

def gen_float32_weights(size_kb=256):
    """Generate realistic neural network float32 weights."""
    n_floats = (size_kb * 1024) // 4
    # Mix of weight distributions typical in neural nets
    weights = np.concatenate([
        np.random.normal(0, 0.02, n_floats // 4).astype(np.float32),    # Linear layers
        np.random.normal(0, 0.1, n_floats // 4).astype(np.float32),     # Conv layers
        np.ones(n_floats // 8, dtype=np.float32),                        # LayerNorm gamma
        np.zeros(n_floats // 8, dtype=np.float32),                       # LayerNorm beta
        np.random.uniform(-1, 1, n_floats // 4).astype(np.float32),     # Embeddings
    ])
    return weights.tobytes()

def gen_float16_weights(size_kb=128):
    """Generate float16 model weights."""
    n_floats = (size_kb * 1024) // 2
    weights = np.random.normal(0, 0.05, n_floats).astype(np.float16)
    return weights.tobytes()

def gen_mixed_binary(size_kb=64):
    """Generate mixed binary data (headers + structured + random)."""
    parts = []
    # Structured header
    parts.append(b"HEADER\x00\x01\x02\x03" * 100)
    # Repeated patterns
    parts.append(bytes(range(256)) * (size_kb * 2))
    # Some randomness
    parts.append(os.urandom(size_kb * 256))
    data = b"".join(parts)
    return data[:size_kb * 1024]

def gen_xml_data(size_kb=32):
    """Generate XML configuration data."""
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
    i = 0
    while len(xml) < size_kb * 1024:
        xml += f'  <layer id="{i}" type="linear" in_features="{512+i}" out_features="{256+i}">\n'
        xml += f'    <weight_init method="kaiming" gain="1.0"/>\n'
        xml += f'    <bias_init method="zeros"/>\n'
        xml += f'    <dropout rate="0.1"/>\n'
        xml += f'  </layer>\n'
        i += 1
    xml += '</config>'
    return xml[:size_kb * 1024].encode("utf-8")

# ============================================================================
# Benchmark Runner
# ============================================================================

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def compress_and_verify_lattice(src_path, tmp_dir):
    """Compress with Lattice engine and verify lossless roundtrip."""
    archive_path = os.path.join(tmp_dir, "test.lattice")
    decomp_dir = os.path.join(tmp_dir, "decomp")

    # Read original
    with open(src_path, "rb") as f:
        original_data = f.read()
    original_hash = sha256(original_data)
    original_size = len(original_data)

    # Compress
    t0 = time.perf_counter()
    lattice_archive.LatticeArchiveEngine.compress(src_path, archive_path)
    compress_time = time.perf_counter() - t0

    compressed_size = os.path.getsize(archive_path)

    # Decompress
    t0 = time.perf_counter()
    lattice_archive.LatticeArchiveEngine.decompress(archive_path, decomp_dir)
    decompress_time = time.perf_counter() - t0

    # Verify losslessness
    basename = os.path.basename(src_path)
    restored_path = os.path.join(decomp_dir, basename)
    if os.path.exists(restored_path):
        with open(restored_path, "rb") as f:
            restored_data = f.read()
        restored_hash = sha256(restored_data)
        lossless = (original_hash == restored_hash) and (len(restored_data) == original_size)
    else:
        lossless = False
        restored_hash = "FILE_NOT_FOUND"

    # Cleanup
    if os.path.exists(archive_path): os.remove(archive_path)
    if os.path.exists(decomp_dir): shutil.rmtree(decomp_dir)

    return {
        "compressed_size": compressed_size,
        "ratio": original_size / compressed_size if compressed_size > 0 else 0,
        "compress_time": compress_time,
        "decompress_time": decompress_time,
        "compress_speed_mbps": (original_size / 1024 / 1024) / compress_time if compress_time > 0 else 0,
        "lossless": lossless,
        "original_hash": original_hash,
        "restored_hash": restored_hash if not lossless else "MATCH",
    }

def compress_zstd_max(data):
    t0 = time.perf_counter()
    compressed = zstd.ZstdCompressor(level=22).compress(data)
    elapsed = time.perf_counter() - t0
    return compressed, elapsed

def compress_brotli_max(data):
    t0 = time.perf_counter()
    compressed = brotli.compress(data, quality=11)
    elapsed = time.perf_counter() - t0
    return compressed, elapsed

def run_benchmark():
    print("=" * 80)
    print("  MIDDLEOUT-LATTICE vs ZSTD-MAX vs BROTLI-MAX — COMPREHENSIVE BENCHMARK")
    print("=" * 80)
    print()

    # Generate test files
    test_cases = [
        ("english_text_64KB.txt",     gen_english_text(64)),
        ("english_text_256KB.txt",    gen_english_text(256)),
        ("python_code_32KB.py",       gen_python_code(32)),
        ("python_code_128KB.py",      gen_python_code(128)),
        ("json_logs_64KB.json",       gen_json_data(64)),
        ("json_logs_256KB.json",      gen_json_data(256)),
        ("csv_data_64KB.csv",         gen_csv_data(64)),
        ("html_page_32KB.html",       gen_html_page(32)),
        ("xml_config_32KB.xml",       gen_xml_data(32)),
        ("float32_weights_256KB.bin", gen_float32_weights(256)),
        ("float32_weights_1MB.bin",   gen_float32_weights(1024)),
        ("float16_weights_128KB.bin", gen_float16_weights(128)),
        ("mixed_binary_64KB.bin",     gen_mixed_binary(64)),
    ]

    tmp_dir = tempfile.mkdtemp(prefix="lattice_bench_")
    results = []

    print(f"{'File':<32} {'Size':>8} {'Lattice':>8} {'Zstd22':>8} {'Brotli11':>8} | {'L-Ratio':>7} {'Z-Ratio':>7} {'B-Ratio':>7} | {'L-Time':>7} {'Z-Time':>7} {'B-Time':>7} | {'Lossless':>8}")
    print("-" * 160)

    total_original = 0
    total_lattice = 0
    total_zstd = 0
    total_brotli = 0
    total_lattice_time = 0
    total_zstd_time = 0
    total_brotli_time = 0
    all_lossless = True

    for filename, data in test_cases:
        original_size = len(data)
        total_original += original_size

        # Write test file
        src_path = os.path.join(tmp_dir, filename)
        with open(src_path, "wb") as f:
            f.write(data)

        # Lattice compress + verify
        lattice_result = compress_and_verify_lattice(src_path, tmp_dir)
        lattice_size = lattice_result["compressed_size"]
        lattice_ratio = lattice_result["ratio"]
        lattice_time = lattice_result["compress_time"]
        lossless = lattice_result["lossless"]

        total_lattice += lattice_size
        total_lattice_time += lattice_time
        if not lossless:
            all_lossless = False

        # Zstd max
        zstd_compressed, zstd_time = compress_zstd_max(data)
        zstd_size = len(zstd_compressed)
        zstd_ratio = original_size / zstd_size if zstd_size > 0 else 0
        total_zstd += zstd_size
        total_zstd_time += zstd_time

        # Brotli max
        brotli_compressed, brotli_time = compress_brotli_max(data)
        brotli_size = len(brotli_compressed)
        brotli_ratio = original_size / brotli_size if brotli_size > 0 else 0
        total_brotli += brotli_size
        total_brotli_time += brotli_time

        size_str = f"{original_size/1024:.0f}KB"
        lossless_str = "✓ YES" if lossless else "✗ FAIL"

        print(f"{filename:<32} {size_str:>8} {lattice_size:>8} {zstd_size:>8} {brotli_size:>8} | {lattice_ratio:>7.3f} {zstd_ratio:>7.3f} {brotli_ratio:>7.3f} | {lattice_time:>6.3f}s {zstd_time:>6.3f}s {brotli_time:>6.3f}s | {lossless_str:>8}")

        results.append({
            "file": filename,
            "original_size": original_size,
            "lattice_size": lattice_size,
            "zstd_size": zstd_size,
            "brotli_size": brotli_size,
            "lattice_ratio": round(lattice_ratio, 4),
            "zstd_ratio": round(zstd_ratio, 4),
            "brotli_ratio": round(brotli_ratio, 4),
            "lattice_time": round(lattice_time, 4),
            "zstd_time": round(zstd_time, 4),
            "brotli_time": round(brotli_time, 4),
            "lattice_speed_mbps": round(lattice_result["compress_speed_mbps"], 2),
            "lossless": lossless,
        })

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Summary
    print()
    print("=" * 80)
    print("  AGGREGATE RESULTS")
    print("=" * 80)
    print(f"  Total Original Size:      {total_original:>12,} bytes ({total_original/1024/1024:.2f} MB)")
    print()
    print(f"  Lattice Compressed:       {total_lattice:>12,} bytes  Ratio: {total_original/total_lattice:.4f}x  Time: {total_lattice_time:.3f}s  Speed: {total_original/1024/1024/total_lattice_time:.1f} MB/s")
    print(f"  Zstd Max (Level 22):      {total_zstd:>12,} bytes  Ratio: {total_original/total_zstd:.4f}x  Time: {total_zstd_time:.3f}s  Speed: {total_original/1024/1024/total_zstd_time:.1f} MB/s")
    print(f"  Brotli Max (Quality 11):  {total_brotli:>12,} bytes  Ratio: {total_original/total_brotli:.4f}x  Time: {total_brotli_time:.3f}s  Speed: {total_original/1024/1024/total_brotli_time:.1f} MB/s")
    print()

    lattice_vs_zstd = (1 - total_lattice / total_zstd) * 100
    lattice_vs_brotli = (1 - total_lattice / total_brotli) * 100
    lattice_speed_vs_zstd = total_zstd_time / total_lattice_time if total_lattice_time > 0 else 0
    lattice_speed_vs_brotli = total_brotli_time / total_lattice_time if total_lattice_time > 0 else 0

    print(f"  Lattice vs Zstd-22:    {lattice_vs_zstd:+.2f}% size   {lattice_speed_vs_zstd:.1f}x faster")
    print(f"  Lattice vs Brotli-11:  {lattice_vs_brotli:+.2f}% size   {lattice_speed_vs_brotli:.1f}x faster")
    print()
    print(f"  ALL FILES LOSSLESS:    {'✓ YES — BIT-PERFECT ROUNDTRIP' if all_lossless else '✗ FAILURES DETECTED'}")
    print("=" * 80)

    # Output JSON for artifact
    report = {
        "summary": {
            "total_original": total_original,
            "lattice_total": total_lattice,
            "zstd_total": total_zstd,
            "brotli_total": total_brotli,
            "lattice_ratio": round(total_original / total_lattice, 4),
            "zstd_ratio": round(total_original / total_zstd, 4),
            "brotli_ratio": round(total_original / total_brotli, 4),
            "lattice_time": round(total_lattice_time, 4),
            "zstd_time": round(total_zstd_time, 4),
            "brotli_time": round(total_brotli_time, 4),
            "all_lossless": all_lossless,
        },
        "results": results,
    }

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed results saved to: {report_path}")

if __name__ == "__main__":
    run_benchmark()
