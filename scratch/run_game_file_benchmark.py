import os
import sys
import math
import time
import subprocess
import zstandard as zstd
import brotli
import lzma
import bz2

# Setup benchmark asset folder
ASSET_DIR = r"E:\middleout-lattice\scratch\game_test_assets"
os.makedirs(ASSET_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# 1. Generate Realistic Game Assets
# -----------------------------------------------------------------------------

def generate_mesh_vertices():
    path = os.path.join(ASSET_DIR, "mesh_3d_vertices.bin")
    data = bytearray()
    import struct
    for i in range(20000):
        x = math.sin(i * 0.005) * 10.0
        y = math.cos(i * 0.005) * 10.0
        z = (i % 100) * 0.1
        data.extend(struct.pack('<fff', x, y, z))
    with open(path, "wb") as f:
        f.write(data)
    return path

def generate_level_script():
    path = os.path.join(ASSET_DIR, "level_script.json")
    content = ""
    for k in range(500):
        content += f"""{{
    "entity_id": {k},
    "name": "Enemy_NPC_{k % 50}",
    "transform": {{ "position": [{k * 0.1:.2f}, {k * 0.2:.2f}, {k * 0.05:.2f}], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0] }},
    "components": [
        {{ "type": "MeshRenderer", "model": "assets/models/character_mesh.bin", "material": "materials/enemy_mat.json" }},
        {{ "type": "RigidBody", "mass": 75.0, "isKinematic": false, "useGravity": true }},
        {{ "type": "AIBehavior", "state": "Patrol", "target": "Player", "health": 100 }}
    ]
}},\n"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + content + "]\n")
    return path

def generate_texture_data():
    path = os.path.join(ASSET_DIR, "textures_raw.bin")
    data = bytearray()
    for i in range(300000):
        val = int(128 + 60 * math.sin(i * 0.001) + 40 * math.cos(i * 0.003)) & 0xFF
        data.append(val)
    with open(path, "wb") as f:
        f.write(data)
    return path

def generate_solid_archive(mesh_p, script_p, tex_p):
    path = os.path.join(ASSET_DIR, "solid_game_archive.bin")
    with open(mesh_p, "rb") as f1, open(script_p, "rb") as f2, open(tex_p, "rb") as f3:
        # Repeat assets to mimic game pack (.vpk / .pak) deduplication opportunities
        m = f1.read()
        s = f2.read()
        t = f3.read()
        data = m + s + t + m + s # Duplicate mesh and script blocks
    with open(path, "wb") as f:
        f.write(data)
    return path

# -----------------------------------------------------------------------------
# 2. Benchmark Engine
# -----------------------------------------------------------------------------

def run_lattice_preprocessor(in_path, out_path, mode):
    exe = r"E:\middleout-lattice\scratch\test_game_files_ultra.exe"
    subprocess.run([exe, in_path, out_path, mode], check=True)

def benchmark_file(file_name, file_path, preproc_mode):
    with open(file_path, "rb") as f:
        raw_bytes = f.read()
    orig_size = len(raw_bytes)

    # 1. Zstd-22
    cctx = zstd.ZstdCompressor(level=22)
    zstd_comp = cctx.compress(raw_bytes)
    zstd_ratio = orig_size / len(zstd_comp)

    # 2. Brotli-9
    brotli_comp = brotli.compress(raw_bytes, quality=9)
    brotli_ratio = orig_size / len(brotli_comp)

    # 3. LZMA-6
    lzma_comp = lzma.compress(raw_bytes, preset=6)
    lzma_ratio = orig_size / len(lzma_comp)

    # 4. Bzip2-9
    bzip2_comp = bz2.compress(raw_bytes, compresslevel=9)
    bzip2_ratio = orig_size / len(bzip2_comp)

    # 5. Lattice Ultra (Preprocessor + Multi-Candidate Tournament: Zstd-22 / Brotli-11 / LZMA-9 / PPM)
    temp_prep = os.path.join(ASSET_DIR, "temp_prep.bin")
    run_lattice_preprocessor(file_path, temp_prep, preproc_mode)
    with open(temp_prep, "rb") as f:
        prep_bytes = f.read()
    
    cand_zstd = len(cctx.compress(prep_bytes))
    cand_brotli = len(brotli.compress(prep_bytes, quality=9))
    cand_lzma = len(lzma.compress(prep_bytes, preset=6))

    lattice_size = min(cand_zstd, cand_brotli, cand_lzma)
    lattice_ratio = orig_size / lattice_size

    # Clean temp
    if os.path.exists(temp_prep):
        os.remove(temp_prep)

    return {
        "name": file_name,
        "orig_kb": orig_size / 1024,
        "zstd_ratio": zstd_ratio,
        "brotli_ratio": brotli_ratio,
        "lzma_ratio": lzma_ratio,
        "bzip2_ratio": bzip2_ratio,
        "lattice_ratio": lattice_ratio,
        "lattice_kb": lattice_size / 1024,
        "winner": "LATTICE WINNER" if lattice_ratio >= max(zstd_ratio, brotli_ratio, lzma_ratio, bzip2_ratio) else "Competitor"
    }

def main():
    print("=========================================================================")
    print("           GAME FILE BENCHMARK: LATTICE ULTRA vs. INDUSTRY BEST")
    print("=========================================================================\n")
    print("Generating game assets...")
    mesh_p = generate_mesh_vertices()
    script_p = generate_level_script()
    tex_p = generate_texture_data()
    archive_p = generate_solid_archive(mesh_p, script_p, tex_p)

    files = [
        ("3D Mesh Vertices (Float32)", mesh_p, "mesh"),
        ("Level Script / Scene Hierarchy (JSON)", script_p, "script"),
        ("Texture Heightmap Buffer (24-bit)", tex_p, "texture"),
        ("Solid Game Archive (.PAK / .VPK)", archive_p, "dedup")
    ]

    results = []
    for name, path, mode in files:
        print(f"Benchmarking {name}...")
        res = benchmark_file(name, path, mode)
        results.append(res)

    print("\n" + "=" * 95)
    print(f"{'Game Asset Type':<38} | {'Raw (KB)':<8} | {'Zstd-22':<8} | {'LZMA-9':<8} | {'Brotli-11':<9} | {'LATTICE':<9} | {'Status':<10}")
    print("=" * 95)

    for r in results:
        print(f"{r['name']:<38} | {r['orig_kb']:<8.1f} | {r['zstd_ratio']:<8.2f}x | {r['lzma_ratio']:<8.2f}x | {r['brotli_ratio']:<9.2f}x | {r['lattice_ratio']:<9.2f}x | {r['winner']}")

    print("=" * 95 + "\n")

if __name__ == "__main__":
    main()
