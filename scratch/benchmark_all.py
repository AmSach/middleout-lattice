#!/usr/bin/env python3
"""
Comprehensive Lattice Benchmark — vs Zstd, LZMA, Brotli, gzip, bz2
Tests: Canterbury Corpus, Text, Code, JSON, Game Files (with duplicates), ML Weights
"""
import os, sys, io, time, struct, json, shutil, tempfile, zlib, bz2, lzma

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lattice_archive

try:
    import zstandard as zstd
except ImportError:
    zstd = None

try:
    import brotli
except ImportError:
    brotli = None

# ──── Helpers ────────────────────────────────────────────────────────────────

def compress_with_lattice(src_dir, solid=True):
    """Compress a directory with Lattice, return (compressed_size, elapsed_sec)."""
    archive_path = src_dir + ".lat"
    t0 = time.perf_counter()
    mode, orig, nfiles = lattice_archive.LatticeArchiveEngine.compress(
        src_dir, archive_path, virtually_lossless=0, solid=solid
    )
    elapsed = time.perf_counter() - t0
    comp_size = os.path.getsize(archive_path)
    # Verify decompression
    dest = src_dir + "_verify"
    lattice_archive.LatticeArchiveEngine.decompress(archive_path, dest)
    # Verify files match
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            orig_path = os.path.join(root, f)
            rel = os.path.relpath(orig_path, src_dir)
            ver_path = os.path.join(dest, rel)
            if os.path.exists(ver_path):
                if open(orig_path, "rb").read() != open(ver_path, "rb").read():
                    print(f"  ⚠ MISMATCH: {rel}")
    shutil.rmtree(dest, ignore_errors=True)
    os.remove(archive_path)
    return comp_size, elapsed

def compress_with_lattice_file(data_bytes, filename="data.txt"):
    """Compress raw bytes with Lattice (wraps in temp dir)."""
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "src")
    os.makedirs(src)
    with open(os.path.join(src, filename), "wb") as f:
        f.write(data_bytes)
    comp_size, elapsed = compress_with_lattice(src, solid=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return comp_size, elapsed

def compress_with_zstd(data, level=9):
    if not zstd: return None, 0
    t0 = time.perf_counter()
    cctx = zstd.ZstdCompressor(level=level)
    compressed = cctx.compress(data)
    return len(compressed), time.perf_counter() - t0

def compress_with_zstd_max(data):
    if not zstd: return None, 0
    return compress_with_zstd(data, level=22)

def compress_with_lzma(data):
    t0 = time.perf_counter()
    compressed = lzma.compress(data, preset=9)
    return len(compressed), time.perf_counter() - t0

def compress_with_brotli(data, quality=11):
    if not brotli: return None, 0
    t0 = time.perf_counter()
    compressed = brotli.compress(data, quality=quality)
    return len(compressed), time.perf_counter() - t0

def compress_with_gzip(data, level=9):
    t0 = time.perf_counter()
    compressed = zlib.compress(data, level)
    return len(compressed), time.perf_counter() - t0

def compress_with_bz2(data, level=9):
    t0 = time.perf_counter()
    compressed = bz2.compress(data, compresslevel=level)
    return len(compressed), time.perf_counter() - t0

def fmt_ratio(orig, comp):
    if comp is None or comp == 0: return "N/A"
    return f"{orig/comp:.2f}x"

def fmt_speed(orig, elapsed):
    if elapsed == 0: return "∞"
    mbps = (orig / 1024 / 1024) / elapsed
    return f"{mbps:.1f} MB/s"

def run_single_file_benchmark(name, data, filename=None):
    """Run all compressors on a single file's bytes."""
    orig = len(data)
    results = {}

    # Lattice (via temp dir)
    lat_size, lat_time = compress_with_lattice_file(data, filename or (name if '.' in name else "data.txt"))
    results["Lattice"] = (lat_size, lat_time)

    # Zstd-9
    zs9, zt9 = compress_with_zstd(data, 9)
    results["Zstd-9"] = (zs9, zt9)

    # Zstd-22
    zs22, zt22 = compress_with_zstd_max(data)
    results["Zstd-22"] = (zs22, zt22)

    # LZMA-9
    ls, lt = compress_with_lzma(data)
    results["LZMA-9"] = (ls, lt)

    # Brotli-11
    bs, bt = compress_with_brotli(data)
    results["Brotli-11"] = (bs, bt)

    # gzip-9
    gs, gt = compress_with_gzip(data)
    results["gzip-9"] = (gs, gt)

    # bz2-9
    b2s, b2t = compress_with_bz2(data)
    results["bz2-9"] = (b2s, b2t)

    print(f"\n  {'Compressor':<14} {'Compressed':>12} {'Ratio':>8} {'Speed':>12}")
    print(f"  {'─'*14} {'─'*12} {'─'*8} {'─'*12}")
    for cname, (csize, ctime) in results.items():
        if csize is not None:
            print(f"  {cname:<14} {csize:>10,} B {fmt_ratio(orig, csize):>8} {fmt_speed(orig, ctime):>12}")
        else:
            print(f"  {cname:<14} {'N/A':>12} {'N/A':>8} {'N/A':>12}")

    return results

def run_directory_benchmark(name, src_dir):
    """Run Lattice on a directory; run other compressors on concatenated bytes."""
    # Compute total size
    all_bytes = bytearray()
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d != '.git']
        for f in files:
            fp = os.path.join(root, f)
            try:
                all_bytes.extend(open(fp, "rb").read())
            except: pass
    orig = len(all_bytes)
    data = bytes(all_bytes)

    results = {}

    # Lattice (directory-level, gets dedup benefits)
    lat_size, lat_time = compress_with_lattice(src_dir, solid=True)
    results["Lattice"] = (lat_size, lat_time)

    # Other compressors on concatenated bytes
    zs9, zt9 = compress_with_zstd(data, 9)
    results["Zstd-9"] = (zs9, zt9)
    zs22, zt22 = compress_with_zstd_max(data)
    results["Zstd-22"] = (zs22, zt22)
    ls, lt = compress_with_lzma(data)
    results["LZMA-9"] = (ls, lt)
    bs, bt = compress_with_brotli(data)
    results["Brotli-11"] = (bs, bt)
    gs, gt = compress_with_gzip(data)
    results["gzip-9"] = (gs, gt)
    b2s, b2t = compress_with_bz2(data)
    results["bz2-9"] = (b2s, b2t)

    print(f"\n  {'Compressor':<14} {'Compressed':>12} {'Ratio':>8} {'Speed':>12}")
    print(f"  {'─'*14} {'─'*12} {'─'*8} {'─'*12}")
    for cname, (csize, ctime) in results.items():
        if csize is not None:
            print(f"  {cname:<14} {csize:>10,} B {fmt_ratio(orig, csize):>8} {fmt_speed(orig, ctime):>12}")
        else:
            print(f"  {cname:<14} {'N/A':>12} {'N/A':>8} {'N/A':>12}")

    return orig, results


# ──── Generate Synthetic Test Datasets ───────────────────────────────────────

def generate_json_dataset(path, size_kb=512):
    """Generate realistic structured JSON data."""
    os.makedirs(path, exist_ok=True)
    records = []
    for i in range(size_kb * 2):
        records.append({
            "id": i,
            "name": f"user_{i:06d}",
            "email": f"user_{i:06d}@example.com",
            "address": {
                "street": f"{i * 7 % 999} Main Street",
                "city": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"][i % 5],
                "state": ["NY", "CA", "IL", "TX", "AZ"][i % 5],
                "zip": f"{10000 + i % 90000}"
            },
            "scores": [round(i * 0.1 % 100, 2), round(i * 0.3 % 100, 2), round(i * 0.7 % 100, 2)],
            "active": i % 3 != 0,
            "tags": ["premium", "verified"] if i % 4 == 0 else ["standard"],
            "metadata": {"created": f"2026-01-{(i%28)+1:02d}", "version": "1.0"}
        })
    with open(os.path.join(path, "users.json"), "w") as f:
        json.dump(records, f, indent=2)
    
    # Config-style JSON  
    config = {
        "application": {
            "name": "MiddleoutApp",
            "version": "3.0.0",
            "features": {f"feature_{i}": {"enabled": i % 2 == 0, "config": {"threshold": 0.5 + i * 0.01}} for i in range(100)}
        }
    }
    with open(os.path.join(path, "config.json"), "w") as f:
        json.dump(config, f, indent=2)


def generate_code_dataset(path, size_kb=256):
    """Generate realistic source code files."""
    os.makedirs(path, exist_ok=True)
    
    # Python
    py_code = []
    for i in range(size_kb // 4):
        py_code.append(f'''
class DataProcessor_{i}:
    """Process data records for pipeline stage {i}."""
    
    def __init__(self, config=None):
        self.config = config or {{}}
        self.buffer = []
        self.processed_count = 0
    
    def process(self, record):
        """Process a single record through the pipeline."""
        if not isinstance(record, dict):
            raise TypeError(f"Expected dict, got {{type(record).__name__}}")
        
        result = {{
            "id": record.get("id", self.processed_count),
            "timestamp": record.get("timestamp", ""),
            "value": self._transform(record.get("value", 0)),
            "status": "processed"
        }}
        self.buffer.append(result)
        self.processed_count += 1
        return result
    
    def _transform(self, value):
        """Apply transformation to value."""
        threshold = self.config.get("threshold", {0.5 + i * 0.01})
        return value * threshold if value > 0 else 0
    
    def flush(self):
        """Flush buffer to output."""
        output = list(self.buffer)
        self.buffer.clear()
        return output
''')
    with open(os.path.join(path, "processors.py"), "w") as f:
        f.write("\n".join(py_code))
    
    # C++ header
    cpp_code = ['#pragma once\n#include <vector>\n#include <string>\n#include <memory>\n#include <algorithm>\n\nnamespace lattice {\n']
    for i in range(size_kb // 8):
        cpp_code.append(f'''
template<typename T>
class Container_{i} {{
public:
    Container_{i}() = default;
    ~Container_{i}() = default;
    
    void push_back(const T& value) {{ data_.push_back(value); }}
    void push_back(T&& value) {{ data_.push_back(std::move(value)); }}
    
    size_t size() const {{ return data_.size(); }}
    bool empty() const {{ return data_.empty(); }}
    
    T& operator[](size_t idx) {{ return data_[idx]; }}
    const T& operator[](size_t idx) const {{ return data_[idx]; }}
    
    void sort() {{ std::sort(data_.begin(), data_.end()); }}
    
    auto begin() {{ return data_.begin(); }}
    auto end() {{ return data_.end(); }}
    
private:
    std::vector<T> data_;
    std::string name_ = "container_{i}";
}};
''')
    cpp_code.append('} // namespace lattice\n')
    with open(os.path.join(path, "containers.hpp"), "w") as f:
        f.write("\n".join(cpp_code))


def generate_game_files(path, num_textures=20, texture_size_kb=64):
    """Generate game-like files with duplicate assets (textures, meshes, audio stubs)."""
    os.makedirs(os.path.join(path, "textures"), exist_ok=True)
    os.makedirs(os.path.join(path, "meshes"), exist_ok=True)
    os.makedirs(os.path.join(path, "audio"), exist_ok=True)
    os.makedirs(os.path.join(path, "levels"), exist_ok=True)
    
    import random
    random.seed(42)
    
    # Create base textures (some will be duplicated)
    unique_textures = []
    for i in range(num_textures // 3):
        data = bytes(random.getrandbits(8) for _ in range(texture_size_kb * 1024))
        unique_textures.append(data)
    
    # Write textures — many are duplicates (simulating multi-level reuse)
    for i in range(num_textures):
        idx = i % len(unique_textures)  # Cycle through unique textures = duplicates!
        fname = f"texture_{i:03d}.dds"
        with open(os.path.join(path, "textures", fname), "wb") as f:
            f.write(unique_textures[idx])
    
    # Mesh data — semi-structured float arrays (vertices)
    for i in range(8):
        mesh = bytearray()
        for v in range(1024):
            for _ in range(3):  # x, y, z
                mesh.extend(struct.pack("<f", random.uniform(-100.0, 100.0)))
        with open(os.path.join(path, "meshes", f"mesh_{i:03d}.obj"), "wb") as f:
            f.write(mesh)
    
    # Audio stubs — header + repeated waveform pattern
    for i in range(4):
        wave = bytearray(b"RIFF")
        wave.extend(struct.pack("<I", 0))  # placeholder size
        wave.extend(b"WAVEfmt ")
        wave.extend(struct.pack("<I", 16))  # chunk size
        wave.extend(struct.pack("<HHIIHH", 1, 1, 44100, 44100, 1, 8))
        wave.extend(b"data")
        audio_data = bytes([int(127 + 127 * __import__('math').sin(2 * 3.14159 * 440 * t / 44100)) & 0xFF for t in range(44100)])
        wave.extend(struct.pack("<I", len(audio_data)))
        wave.extend(audio_data)
        with open(os.path.join(path, "audio", f"sfx_{i:03d}.wav"), "wb") as f:
            f.write(wave)
    
    # Level config files — JSON (highly compressible, repetitive structures)
    for i in range(6):
        level = {
            "level_id": i,
            "name": f"Level {i+1}",
            "entities": [
                {
                    "id": j,
                    "type": ["enemy", "item", "npc", "trigger"][j % 4],
                    "position": [random.uniform(-500, 500), random.uniform(0, 100), random.uniform(-500, 500)],
                    "rotation": [0, random.uniform(0, 360), 0],
                    "properties": {"health": 100, "damage": 25, "speed": 3.5}
                }
                for j in range(200)
            ]
        }
        with open(os.path.join(path, "levels", f"level_{i:02d}.json"), "w") as f:
            json.dump(level, f, indent=2)


def generate_ml_weights(path, size_mb=2):
    """Generate synthetic ML model weight files (float32 arrays)."""
    os.makedirs(path, exist_ok=True)
    import random
    random.seed(123)
    
    # Float32 weights — typical distribution near zero
    num_floats = (size_mb * 1024 * 1024) // 4
    data = bytearray()
    for _ in range(num_floats):
        val = random.gauss(0, 0.02)  # Typical weight distribution
        data.extend(struct.pack("<f", val))
    
    with open(os.path.join(path, "model_weights.bin"), "wb") as f:
        f.write(data)
    
    # FP16 weights
    import array
    fp16_data = bytearray()
    for _ in range(num_floats // 2):
        val = random.gauss(0, 0.02)
        # Simple FP16 conversion via struct
        fp16_data.extend(struct.pack("<e", val))
    
    with open(os.path.join(path, "model_weights_fp16.bin"), "wb") as f:
        f.write(fp16_data)


# ──── Main Benchmark ─────────────────────────────────────────────────────────

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp_root = os.path.join(base_dir, "benchmark_tmp")
    os.makedirs(tmp_root, exist_ok=True)
    
    all_results = {}
    
    print("=" * 72)
    print(" LATTICE COMPREHENSIVE BENCHMARK — vs Industry Standards")
    print("=" * 72)
    
    # ── 1. Canterbury Corpus ──────────────────────────────────────────────
    print("\n" + "─" * 72)
    print("📚 TEST 1: Canterbury Corpus (Standard Compression Benchmark)")
    cant_dir = os.path.join(base_dir, "local_dataset", "standard_corpora", "canterbury")
    if os.path.isdir(cant_dir):
        # Get total size
        cant_total = sum(os.path.getsize(os.path.join(cant_dir, f)) 
                        for f in os.listdir(cant_dir) if os.path.isfile(os.path.join(cant_dir, f)))
        print(f"   Original size: {cant_total:,} bytes ({cant_total/1024:.1f} KB)")
        orig, results = run_directory_benchmark("Canterbury", cant_dir)
        all_results["Canterbury Corpus"] = {"orig": orig, "results": {k: v[0] for k, v in results.items()}}
    else:
        print("   ⚠ Canterbury corpus not found, skipping")
    
    # ── 2. Text / Literature ─────────────────────────────────────────────
    print("\n" + "─" * 72)
    print("📖 TEST 2: Literature Text (pride.txt — 738 KB)")
    pride_path = os.path.join(base_dir, "local_dataset", "pride.txt")
    if os.path.exists(pride_path):
        data = open(pride_path, "rb").read()
        print(f"   Original size: {len(data):,} bytes")
        results = run_single_file_benchmark("pride.txt", data)
        all_results["Literature Text"] = {"orig": len(data), "results": {k: v[0] for k, v in results.items()}}
    
    # ── 3. Source Code ────────────────────────────────────────────────────
    print("\n" + "─" * 72)
    print("💻 TEST 3: Source Code (stb_image.h — 283 KB C header)")
    stb_path = os.path.join(base_dir, "local_dataset", "stb_image.h")
    if os.path.exists(stb_path):
        data = open(stb_path, "rb").read()
        print(f"   Original size: {len(data):,} bytes")
        results = run_single_file_benchmark("stb_image.h", data)
        all_results["Source Code"] = {"orig": len(data), "results": {k: v[0] for k, v in results.items()}}
    
    # ── 4. Generated JSON ────────────────────────────────────────────────
    print("\n" + "─" * 72)
    print("📋 TEST 4: Structured JSON Data (~512 KB)")
    json_dir = os.path.join(tmp_root, "json_data")
    generate_json_dataset(json_dir, size_kb=512)
    json_total = sum(os.path.getsize(os.path.join(json_dir, f)) 
                    for f in os.listdir(json_dir) if os.path.isfile(os.path.join(json_dir, f)))
    print(f"   Original size: {json_total:,} bytes")
    orig, results = run_directory_benchmark("JSON", json_dir)
    all_results["Structured JSON"] = {"orig": orig, "results": {k: v[0] for k, v in results.items()}}
    
    # ── 5. Generated Source Code ──────────────────────────────────────────
    print("\n" + "─" * 72)
    print("🔧 TEST 5: Generated Source Code (~256 KB Python + C++)")
    code_dir = os.path.join(tmp_root, "code_data")
    generate_code_dataset(code_dir, size_kb=256)
    code_total = sum(os.path.getsize(os.path.join(code_dir, f)) 
                    for f in os.listdir(code_dir) if os.path.isfile(os.path.join(code_dir, f)))
    print(f"   Original size: {code_total:,} bytes")
    orig, results = run_directory_benchmark("Code", code_dir)
    all_results["Source Code (Gen)"] = {"orig": orig, "results": {k: v[0] for k, v in results.items()}}
    
    # ── 6. Game Files with Duplicates ─────────────────────────────────────
    print("\n" + "─" * 72)
    print("🎮 TEST 6: Game Files with Duplicate Assets (~1.7 MB)")
    game_dir = os.path.join(tmp_root, "game_data")
    generate_game_files(game_dir, num_textures=20, texture_size_kb=64)
    game_total = 0
    for root, dirs, files in os.walk(game_dir):
        for f in files:
            game_total += os.path.getsize(os.path.join(root, f))
    print(f"   Original size: {game_total:,} bytes ({game_total/1024/1024:.1f} MB)")
    print(f"   Contains: 20 textures (only 7 unique), 8 meshes, 4 audio, 6 level configs")
    orig, results = run_directory_benchmark("Game Files", game_dir)
    all_results["Game Files (Dedup)"] = {"orig": orig, "results": {k: v[0] for k, v in results.items()}}
    
    # ── 7. ML Weights (Float32/FP16) ──────────────────────────────────────
    print("\n" + "─" * 72)
    print("🧠 TEST 7: ML Model Weights (2 MB FP32 + 1 MB FP16)")
    ml_dir = os.path.join(tmp_root, "ml_weights")
    generate_ml_weights(ml_dir, size_mb=2)
    ml_total = sum(os.path.getsize(os.path.join(ml_dir, f)) 
                  for f in os.listdir(ml_dir) if os.path.isfile(os.path.join(ml_dir, f)))
    print(f"   Original size: {ml_total:,} bytes ({ml_total/1024/1024:.1f} MB)")
    orig, results = run_directory_benchmark("ML Weights", ml_dir)
    all_results["ML Weights (FP32+FP16)"] = {"orig": orig, "results": {k: v[0] for k, v in results.items()}}
    
    # ── 8. minGPT Code Repository ─────────────────────────────────────────
    print("\n" + "─" * 72)
    print("🤖 TEST 8: minGPT Repository (real-world code project)")
    mingpt_dir = os.path.join(base_dir, "local_dataset", "minGPT")
    if os.path.isdir(mingpt_dir):
        mgpt_total = 0
        for root, dirs, files in os.walk(mingpt_dir):
            dirs[:] = [d for d in dirs if d != '.git']
            for f in files:
                try:
                    mgpt_total += os.path.getsize(os.path.join(root, f))
                except: pass
        print(f"   Original size: {mgpt_total:,} bytes ({mgpt_total/1024:.1f} KB)")
        # Copy without .git
        mgpt_clean = os.path.join(tmp_root, "minGPT_clean")
        if os.path.exists(mgpt_clean):
            shutil.rmtree(mgpt_clean)
        shutil.copytree(mingpt_dir, mgpt_clean, ignore=shutil.ignore_patterns('.git'))
        orig, results = run_directory_benchmark("minGPT", mgpt_clean)
        all_results["minGPT Repository"] = {"orig": orig, "results": {k: v[0] for k, v in results.items()}}
    
    # ══════ SUMMARY TABLE ═════════════════════════════════════════════════
    print("\n" + "═" * 72)
    print(" FINAL RESULTS — COMPRESSION RATIO COMPARISON (higher = better)")
    print("═" * 72)
    
    compressors = ["Lattice", "Zstd-9", "Zstd-22", "LZMA-9", "Brotli-11", "gzip-9", "bz2-9"]
    
    # Header
    hdr = f"{'Dataset':<22}"
    for c in compressors:
        hdr += f" {c:>9}"
    print(hdr)
    print("─" * 22 + " " + " ".join(["─" * 9] * len(compressors)))
    
    lattice_wins = 0
    total_tests = 0
    
    for dname, dinfo in all_results.items():
        orig = dinfo["orig"]
        row = f"{dname:<22}"
        best_ratio = 0
        best_name = ""
        for c in compressors:
            csize = dinfo["results"].get(c)
            if csize and csize > 0:
                ratio = orig / csize
                row += f" {ratio:>8.2f}x"
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_name = c
            else:
                row += f" {'N/A':>9}"
        
        # Mark winner
        if best_name == "Lattice":
            row += "  🏆"
            lattice_wins += 1
        total_tests += 1
        
        print(row)
    
    print("─" * 22 + " " + " ".join(["─" * 9] * len(compressors)))
    print(f"\n🏆 Lattice wins {lattice_wins}/{total_tests} categories")
    
    # Cleanup
    print(f"\nCleaning up benchmark temp files...")
    shutil.rmtree(tmp_root, ignore_errors=True)
    
    print("\n" + "═" * 72)
    print(" BENCHMARK COMPLETE")
    print("═" * 72)
    
    return all_results

if __name__ == "__main__":
    main()
