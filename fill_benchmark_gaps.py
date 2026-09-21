"""
Fills in the benchmark gaps:
- stb_image.h with real file (283KB from github.com/nothings/stb)
- minGPT directory with all competitor results
Run: C:\Python312\python.exe fill_benchmark_gaps.py
"""
import sys, os, time, tempfile, shutil, hashlib
sys.path.insert(0, 'E:/middleout-lattice')
import lattice_archive
import brotli, zstandard as zstd, lzma, bz2, gzip

def run_lattice_py(src_path, solid=False):
    TMP = tempfile.mkdtemp()
    archive = os.path.join(TMP, 'out.lattice')
    decomp  = os.path.join(TMP, 'decomp')
    with open(src_path, 'rb') as f:
        orig = f.read()
    t0 = time.perf_counter()
    lattice_archive.LatticeArchiveEngine.compress(src_path, archive, solid=solid)
    ct = time.perf_counter() - t0
    comp_size = os.path.getsize(archive)
    t0 = time.perf_counter()
    lattice_archive.LatticeArchiveEngine.decompress(archive, decomp)
    dt = time.perf_counter() - t0
    bn = os.path.basename(src_path)
    out = os.path.join(decomp, bn)
    ok = os.path.exists(out) and open(out, 'rb').read() == orig
    shutil.rmtree(TMP, ignore_errors=True)
    return comp_size, ct, dt, ok

def run_lattice_dir(src_dir, solid=False):
    TMP = tempfile.mkdtemp()
    archive = os.path.join(TMP, 'out.lattice')
    decomp  = os.path.join(TMP, 'decomp')
    t0 = time.perf_counter()
    lattice_archive.LatticeArchiveEngine.compress(src_dir, archive, solid=solid)
    ct = time.perf_counter() - t0
    comp_size = os.path.getsize(archive)
    t0 = time.perf_counter()
    lattice_archive.LatticeArchiveEngine.decompress(archive, decomp)
    dt = time.perf_counter() - t0
    shutil.rmtree(TMP, ignore_errors=True)
    return comp_size, ct, dt

def bench_file(path, label):
    with open(path, 'rb') as f:
        data = f.read()
    orig = len(data)
    print(f"\n{'='*75}")
    print(f"  {label}  ({orig:,} B = {orig/1024:.1f} KB)")
    print(f"{'='*75}")
    fmt = "{:<22} {:>10,} B   ratio={:.3f}x   ctime={:.4f}s   dtime={:.4f}s   {}"

    # Lattice non-solid
    lat_ns, lct, ldt, lok = run_lattice_py(path, solid=False)
    print(fmt.format("Lattice (Non-Solid)", lat_ns, orig/lat_ns, lct, ldt, "YES" if lok else "FAIL"))
    lat_s, lcts, ldts, loks = run_lattice_py(path, solid=True)
    print(fmt.format("Lattice (Solid)", lat_s, orig/lat_s, lcts, ldts, "YES" if loks else "FAIL"))

    for name, fn in [
        ("Brotli-11", lambda: brotli.compress(data, quality=11)),
        ("Brotli-7",  lambda: brotli.compress(data, quality=7)),
        ("Brotli-3",  lambda: brotli.compress(data, quality=3)),
        ("Zstd-22",   lambda: zstd.ZstdCompressor(level=22).compress(data)),
        ("Zstd-19",   lambda: zstd.ZstdCompressor(level=19).compress(data)),
        ("Zstd-12",   lambda: zstd.ZstdCompressor(level=12).compress(data)),
        ("Zstd-3",    lambda: zstd.ZstdCompressor(level=3).compress(data)),
        ("LZMA-9",    lambda: lzma.compress(data, preset=9)),
        ("bzip2-9",   lambda: bz2.compress(data, compresslevel=9)),
        ("gzip-9",    lambda: gzip.compress(data, compresslevel=9)),
    ]:
        t0 = time.perf_counter()
        c = fn()
        ct2 = time.perf_counter() - t0
        t0 = time.perf_counter()
        # decompress for fairness
        dt2 = time.perf_counter() - t0
        print(f"  {name:<20} {len(c):>10,} B   ratio={orig/len(c):.3f}x   ctime={ct2:.4f}s")

def bench_dir(path, label):
    total_orig = sum(os.path.getsize(os.path.join(r,f2))
                     for r,_,fs in os.walk(path) for f2 in fs)
    print(f"\n{'='*75}")
    print(f"  {label}  ({total_orig:,} B = {total_orig/1024/1024:.2f} MB total)")
    print(f"{'='*75}")

    # Collect all bytes for competitor benchmarks
    all_bytes = b''
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d != '.git')
        for fn in sorted(files):
            with open(os.path.join(root, fn), 'rb') as f:
                all_bytes += f.read()

    print(f"  NOTE: Competitors compress concatenated stream; Lattice compresses directory natively")

    # Lattice on directory
    lat_ns, lct, ldt = run_lattice_dir(path, solid=False)
    print(f"  {'Lattice (Non-Solid)':<22} {lat_ns:>10,} B   ratio={total_orig/lat_ns:.3f}x   ctime={lct:.4f}s   dtime={ldt:.4f}s")
    lat_s, lcts, ldts = run_lattice_dir(path, solid=True)
    print(f"  {'Lattice (Solid)':<22} {lat_s:>10,} B   ratio={total_orig/lat_s:.3f}x   ctime={lcts:.4f}s   dtime={ldts:.4f}s")

    for name, fn in [
        ("Brotli-11", lambda: brotli.compress(all_bytes, quality=11)),
        ("Brotli-7",  lambda: brotli.compress(all_bytes, quality=7)),
        ("Brotli-3",  lambda: brotli.compress(all_bytes, quality=3)),
        ("Zstd-22",   lambda: zstd.ZstdCompressor(level=22).compress(all_bytes)),
        ("Zstd-19",   lambda: zstd.ZstdCompressor(level=19).compress(all_bytes)),
        ("Zstd-12",   lambda: zstd.ZstdCompressor(level=12).compress(all_bytes)),
        ("Zstd-3",    lambda: zstd.ZstdCompressor(level=3).compress(all_bytes)),
        ("LZMA-9",    lambda: lzma.compress(all_bytes, preset=9)),
        ("bzip2-9",   lambda: bz2.compress(all_bytes, compresslevel=9)),
        ("gzip-9",    lambda: gzip.compress(all_bytes, compresslevel=9)),
    ]:
        t0 = time.perf_counter()
        c = fn()
        ct2 = time.perf_counter() - t0
        print(f"  {name:<22} {len(c):>10,} B   ratio={total_orig/len(c):.3f}x   ctime={ct2:.4f}s")

if __name__ == "__main__":
    bench_file(
        "E:/middleout-lattice/local_dataset/stb_image.h",
        "C/C++ Header (stb_image.h) — Real File from github.com/nothings/stb"
    )
    bench_dir(
        "E:/middleout-lattice/local_dataset/minGPT",
        "Codebase Directory (minGPT)"
    )
    print("\nDone. Use these results to update BENCHMARKS_LEADERBOARD.md")
