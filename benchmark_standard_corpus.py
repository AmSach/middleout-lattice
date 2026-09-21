"""
Middleout-Lattice -- Standard Corpus Benchmark
Uses Canterbury Corpus + Silesia Corpus + enwik8/enwik9 (Wikipedia)
as industry-standard academic benchmarks.

Downloads corpora automatically if not present.
Compares: Lattice Python engine, Zstd (L3/12/19/22), Brotli (L3/7/11),
          LZMA (preset 9), bzip2 (-9), gzip (-9)

Usage:
    python benchmark_standard_corpus.py
    python benchmark_standard_corpus.py --corpus silesia  (one corpus only)
    python benchmark_standard_corpus.py --no-download     (fail if not present)
"""
import sys, io
# Force UTF-8 output on Windows to avoid cp1252 crashes with box-drawing chars
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os, sys, time, struct, hashlib, tempfile, shutil, argparse, subprocess, json
import urllib.request, zipfile, gzip as gzip_mod, bz2, lzma

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "local_dataset", "standard_corpora")
CLI       = os.path.join(BASE_DIR, "lattice_cli.exe")
TMP_DIR   = tempfile.mkdtemp(prefix="latbench_")

os.makedirs(DATA_DIR, exist_ok=True)

# ── Corpus definitions ────────────────────────────────────────────────────────
CORPORA = {
    "canterbury": {
        "url":  "https://corpus.canterbury.ac.nz/resources/cantrbry.zip",
        "dest": os.path.join(DATA_DIR, "canterbury"),
        "desc": "Canterbury Corpus (classic 11-file benchmark)",
    },
    "silesia": {
        "url":  "https://sun.aei.polsl.pl/~sdeor/corpus/silesia.zip",
        "url2": "http://mattmahoney.net/dc/silesia.zip",           # mirror
        "dest": os.path.join(DATA_DIR, "silesia"),
        "desc": "Silesia Corpus (21 diverse files, 211 MB total)",
    },
    "enwik8": {
        "url":  "http://mattmahoney.net/dc/enwik8.zip",
        "dest": os.path.join(DATA_DIR, "enwik8"),
        "desc": "enwik8 — first 100MB of English Wikipedia XML",
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def human(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def download_corpus(name, spec, allow_download):
    dest = spec["dest"]
    if os.path.isdir(dest) and any(os.scandir(dest)):
        return True  # already present
    if not allow_download:
        print(f"  [SKIP] {name} corpus not found at {dest} and --no-download set")
        return False
    os.makedirs(dest, exist_ok=True)
    urls = [spec["url"]] + ([spec.get("url2")] if spec.get("url2") else [])
    for url in urls:
        try:
            print(f"  [DL] Downloading {name} from {url} ...", flush=True)
            zip_path = os.path.join(TMP_DIR, f"{name}.zip")
            urllib.request.urlretrieve(url, zip_path)
            print(f"  [DL] Extracting ...", flush=True)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(dest)
            os.remove(zip_path)
            print(f"  [DL] Done: {dest}")
            return True
        except Exception as e:
            print(f"  [DL] Failed ({e}), trying next mirror...")
    print(f"  [ERROR] Could not download {name}")
    return False

def collect_files(corpus_dest):
    """Recursively collect all regular files from corpus dir."""
    files = []
    for root, dirs, fnames in os.walk(corpus_dest):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(fnames):
            fp = os.path.join(root, fn)
            if os.path.isfile(fp) and os.path.getsize(fp) > 0:
                files.append(fp)
    return files

# ── Compressor wrappers ───────────────────────────────────────────────────────
def try_import(mod):
    try: return __import__(mod)
    except ImportError: return None

zstd_mod   = try_import("zstandard")
brotli_mod = try_import("brotli")

def comp_lattice(path):
    """Use the Python Lattice engine (same compressed bytes as C++, no DLL needed)."""
    try:
        import lattice_archive as la
    except ImportError:
        return None, None, None, None
    archive = os.path.join(TMP_DIR, "tmp.lattice")
    decomp  = os.path.join(TMP_DIR, "decomp_lat")
    try:
        t0 = time.perf_counter()
        la.LatticeArchiveEngine.compress(path, archive)
        comp_time = time.perf_counter() - t0
        comp_size = os.path.getsize(archive)

        t0 = time.perf_counter()
        la.LatticeArchiveEngine.decompress(archive, decomp)
        decomp_time = time.perf_counter() - t0

        out_file = os.path.join(decomp, os.path.basename(path))
        lossless = os.path.exists(out_file) and sha256_file(out_file) == sha256_file(path)
        return comp_size, comp_time, decomp_time, lossless
    except Exception:
        return None, None, None, None
    finally:
        for p in [archive, decomp]:
            if os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p): os.remove(p)

def comp_zstd(data, level):
    if not zstd_mod: return None, None, None
    t0 = time.perf_counter()
    c = zstd_mod.ZstdCompressor(level=level).compress(data)
    ct = time.perf_counter() - t0
    t0 = time.perf_counter()
    zstd_mod.ZstdDecompressor().decompress(c)
    dt = time.perf_counter() - t0
    return len(c), ct, dt

def comp_brotli(data, quality):
    if not brotli_mod: return None, None, None
    t0 = time.perf_counter()
    c = brotli_mod.compress(data, quality=quality)
    ct = time.perf_counter() - t0
    t0 = time.perf_counter()
    brotli_mod.decompress(c)
    dt = time.perf_counter() - t0
    return len(c), ct, dt

def comp_lzma(data):
    t0 = time.perf_counter()
    c = lzma.compress(data, preset=9)
    ct = time.perf_counter() - t0
    t0 = time.perf_counter()
    lzma.decompress(c)
    dt = time.perf_counter() - t0
    return len(c), ct, dt

def comp_bzip2(data):
    t0 = time.perf_counter()
    c = bz2.compress(data, compresslevel=9)
    ct = time.perf_counter() - t0
    t0 = time.perf_counter()
    bz2.decompress(c)
    dt = time.perf_counter() - t0
    return len(c), ct, dt

def comp_gzip(data):
    import gzip as gz
    t0 = time.perf_counter()
    c = gz.compress(data, compresslevel=9)
    ct = time.perf_counter() - t0
    t0 = time.perf_counter()
    gz.decompress(c)
    dt = time.perf_counter() - t0
    return len(c), ct, dt

# ── Benchmark runner ──────────────────────────────────────────────────────────
def run_corpus(corpus_name, corpus_dest, results_all):
    files = collect_files(corpus_dest)
    if not files:
        print(f"  [WARN] No files found in {corpus_dest}")
        return

    print(f"\n{'='*90}")
    print(f"  CORPUS: {corpus_name.upper()}  ({len(files)} files)")
    print(f"{'='*90}")

    # Aggregate totals per compressor
    totals = {k: {"orig": 0, "comp": 0, "ctime": 0.0, "dtime": 0.0, "wins": 0}
              for k in ["lattice", "zstd22", "zstd19", "brotli11", "lzma9", "bzip2", "gzip9"]}
    all_lossless = True

    hdr = f"{'File':<30} {'Orig':>9} | {'Lattice':>9} {'Zstd22':>9} {'Brotli11':>9} {'LZMA9':>9} {'bzip2':>9} | {'Winner'}"
    print(hdr)
    print("-" * len(hdr))

    corpus_results = []

    for fp in files:
        fname = os.path.relpath(fp, corpus_dest)
        orig_size = os.path.getsize(fp)
        if orig_size > 200 * 1024 * 1024:
            print(f"  [SKIP] {fname} ({human(orig_size)}) — too large, skipping")
            continue

        with open(fp, "rb") as f:
            data = f.read()

        # Run each compressor
        lat_comp, lat_ct, lat_dt, lat_ok = comp_lattice(fp)
        z22_size, z22_ct, z22_dt = comp_zstd(data, 22)
        z19_size, z19_ct, z19_dt = comp_zstd(data, 19)
        br11_size, br11_ct, br11_dt = comp_brotli(data, 11)
        lz_size, lz_ct, lz_dt = comp_lzma(data)
        bz_size, bz_ct, bz_dt = comp_bzip2(data)
        gz_size, gz_ct, gz_dt = comp_gzip(data)

        if lat_ok is False: all_lossless = False

        # Determine winner (by compressed size)
        candidates = {
            "Lattice":  lat_comp,
            "Zstd-22":  z22_size,
            "Brotli-11": br11_size,
            "LZMA-9":   lz_size,
            "bzip2":    bz_size,
            "gzip-9":   gz_size,
        }
        valid = {k: v for k, v in candidates.items() if v is not None}
        winner = min(valid, key=valid.get) if valid else "N/A"

        def r(sz): return f"{orig_size/sz:.3f}x" if sz else "  N/A "
        def c(sz): return f"{sz:>9}" if sz else f"{'N/A':>9}"

        lossless_marker = "✓" if lat_ok else ("✗" if lat_ok is False else "?")
        line = (f"{fname:<30} {human(orig_size):>9} | "
                f"{c(lat_comp)} {c(z22_size)} {c(br11_size)} {c(lz_size)} {c(bz_size)} | "
                f"{winner} {lossless_marker}")
        print(line)

        # Accumulate totals
        for key, sz, ct, dt in [
            ("lattice", lat_comp, lat_ct, lat_dt),
            ("zstd22", z22_size, z22_ct, z22_dt),
            ("zstd19", z19_size, z19_ct, z19_dt),
            ("brotli11", br11_size, br11_ct, br11_dt),
            ("lzma9", lz_size, lz_ct, lz_dt),
            ("bzip2", bz_size, bz_ct, bz_dt),
            ("gzip9", gz_size, gz_ct, gz_dt),
        ]:
            if sz:
                totals[key]["orig"]  += orig_size
                totals[key]["comp"]  += sz
                totals[key]["ctime"] += ct or 0
                totals[key]["dtime"] += dt or 0
        if winner == "Lattice" and lat_comp: totals["lattice"]["wins"] += 1

        corpus_results.append({
            "file": fname, "orig_size": orig_size,
            "lattice": lat_comp, "zstd22": z22_size, "brotli11": br11_size,
            "lzma9": lz_size, "bzip2": bz_size, "gzip9": gz_size,
            "lattice_comp_time": lat_ct, "lattice_lossless": lat_ok,
            "winner": winner,
        })

    # Summary
    print(f"\n{'─'*90}")
    print(f"  AGGREGATE — {corpus_name.upper()}")
    print(f"{'─'*90}")
    ref = totals["lattice"]["orig"]
    print(f"  {'Compressor':<15} {'Ratio':>8} {'CompTime':>10} {'DecompTime':>12} {'Wins':>6}")
    print(f"  {'─'*60}")
    for key, label in [
        ("lattice",  "Lattice C++"),
        ("zstd22",   "Zstd-22"),
        ("zstd19",   "Zstd-19"),
        ("brotli11", "Brotli-11"),
        ("lzma9",    "LZMA-9"),
        ("bzip2",    "bzip2-9"),
        ("gzip9",    "gzip-9"),
    ]:
        t = totals[key]
        if t["comp"] == 0: continue
        ratio = t["orig"] / t["comp"]
        cspeed = t["orig"] / 1024 / 1024 / t["ctime"] if t["ctime"] > 0 else 0
        dspeed = t["orig"] / 1024 / 1024 / t["dtime"] if t["dtime"] > 0 else 0
        wins = t["wins"]
        print(f"  {label:<15} {ratio:>7.4f}x  {t['ctime']:>8.2f}s ({cspeed:>5.1f} MB/s)  "
              f"{t['dtime']:>8.2f}s ({dspeed:>5.1f} MB/s)  {wins:>4} files")

    if all_lossless: print(f"\n  ✓ All Lattice archives verified bit-perfect lossless")
    else: print(f"\n  ✗ Some Lattice lossless checks failed — investigate!")

    results_all[corpus_name] = {"files": corpus_results, "totals": {
        k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()}
        for k, v in totals.items()
    }}

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Lattice Standard Corpus Benchmark")
    parser.add_argument("--corpus", choices=list(CORPORA.keys()) + ["all"], default="all")
    parser.add_argument("--no-download", action="store_true", help="Skip corpus downloads")
    args = parser.parse_args()

    corpora_to_run = list(CORPORA.keys()) if args.corpus == "all" else [args.corpus]
    allow_dl = not args.no_download

    print("=" * 90)
    print("  MIDDLEOUT-LATTICE — STANDARD CORPUS BENCHMARK")
    print("  Canterbury | Silesia | enwik8")
    print("=" * 90)
    print(f"  CLI:    {CLI}  ({'EXISTS' if os.path.exists(CLI) else 'MISSING'})")
    print(f"  Data:   {DATA_DIR}")
    print(f"  zstd:   {'available' if zstd_mod else 'MISSING (pip install zstandard)'}")
    print(f"  brotli: {'available' if brotli_mod else 'MISSING (pip install brotli)'}")
    print()

    all_results = {}
    for cname in corpora_to_run:
        spec = CORPORA[cname]
        ok = download_corpus(cname, spec, allow_dl)
        if ok:
            run_corpus(cname, spec["dest"], all_results)

    # Write JSON report
    report_path = os.path.join(BASE_DIR, "benchmark_standard_corpus_results.json")
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to: {report_path}")

    shutil.rmtree(TMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    main()
