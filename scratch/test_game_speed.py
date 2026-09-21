import os, sys, time, struct, random, shutil
sys.path.insert(0, ".")
import lattice_archive

# Generate a 10MB Game Level Bundle (Textures, Vertices, Level Configs, Audio)
os.makedirs("scratch/game_bundle", exist_ok=True)
random.seed(42)

# 1. Textures with duplicates (4MB)
unique_tex = [bytes(random.getrandbits(8) for _ in range(512 * 1024)) for _ in range(4)]
for i in range(8):
    with open(f"scratch/game_bundle/texture_{i}.dds", "wb") as f:
        f.write(unique_tex[i % 4])

# 2. 3D Vertex Meshes (3MB float32)
mesh_bytes = bytearray()
for v in range(750000):
    mesh_bytes.extend(struct.pack("<fff", random.uniform(-50, 50), random.uniform(0, 20), random.uniform(-50, 50)))
with open("scratch/game_bundle/mesh.obj", "wb") as f:
    f.write(mesh_bytes)

# 3. Level JSON (2MB)
import json
records = [{"id": i, "entity": "enemy_orc", "pos": [i*0.1, i*0.2, i*0.3], "hp": 100} for i in range(30000)]
with open("scratch/game_bundle/level.json", "w") as f:
    json.dump(records, f, indent=2)

total_orig = sum(os.path.getsize(os.path.join("scratch/game_bundle", f)) for f in os.listdir("scratch/game_bundle"))
print(f"Original Game Bundle Size: {total_orig:,} bytes ({total_orig/1024/1024:.2f} MB)")

# Benchmark Lattice Solid Mode
t0 = time.perf_counter()
mode, orig, nfiles = lattice_archive.LatticeArchiveEngine.compress(
    "scratch/game_bundle", "scratch/game_bundle.lattice", solid=True
)
comp_time = time.perf_counter() - t0
comp_size = os.path.getsize("scratch/game_bundle.lattice")

t0 = time.perf_counter()
lattice_archive.LatticeArchiveEngine.decompress("scratch/game_bundle.lattice", "scratch/game_decomp")
decomp_time = time.perf_counter() - t0

ratio = total_orig / comp_size
comp_speed = (total_orig / 1024 / 1024) / comp_time
decomp_speed = (total_orig / 1024 / 1024) / decomp_time

print(f"Lattice Compressed Size: {comp_size:,} bytes")
print(f"Lattice Ratio: {ratio:.2f}x")
print(f"Compression Speed: {comp_speed:.1f} MB/s")
print(f"Decompression Speed: {decomp_speed:.1f} MB/s")

# Clean up
shutil.rmtree("scratch/game_bundle", ignore_errors=True)
shutil.rmtree("scratch/game_decomp", ignore_errors=True)
if os.path.exists("scratch/game_bundle.lattice"): os.remove("scratch/game_bundle.lattice")
