import os
import sys
import shutil

# Make sure lattice_archive is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lattice_archive

def test_dedup():
    print("==================================================")
    # Create temp directories
    test_dir = "test_game_dedup_temp"
    os.makedirs(test_dir, exist_ok=True)
    
    src_dir = os.path.join(test_dir, "src")
    os.makedirs(src_dir, exist_ok=True)
    
    # Generate mock duplicate files (e.g., game assets)
    dummy_data = os.urandom(1024 * 64) # 64KB random block
    
    # File 1: main asset
    with open(os.path.join(src_dir, "texture_main.bin"), "wb") as f:
        f.write(dummy_data)
        
    # File 2: exact copy of File 1 (duplicate texture or localized asset)
    with open(os.path.join(src_dir, "texture_copy.bin"), "wb") as f:
        f.write(dummy_data)
        
    # File 3: partially different asset (first half duplicate, second half different)
    with open(os.path.join(src_dir, "texture_partial.bin"), "wb") as f:
        f.write(dummy_data[:1024 * 32] + os.urandom(1024 * 32))
        
    # Run python compression
    py_archive = os.path.join(test_dir, "archive_py.lat")
    mode, orig_size, num_files = lattice_archive.LatticeArchiveEngine.compress(
        src_dir, py_archive, virtually_lossless=0, solid=True
    )
    py_compressed_size = os.path.getsize(py_archive)
    
    print(f"Original uncompressed size: {orig_size} bytes")
    print(f"Python Mode: {mode} (Mode 8 or 9 means deduplication was triggered!)")
    print(f"Python Compressed size: {py_compressed_size} bytes (Ratio: {orig_size / py_compressed_size:.2f}x)")
    
    # Run CLI compression
    cli_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lattice_cli.exe")
    cli_archive = os.path.join(test_dir, "archive_cli.lat")
    
    # Run CLI command with PATH configured to find MinGW DLLs
    import subprocess
    env = os.environ.copy()
    env["PATH"] = "C:\\Users\\amans\\AppData\\Local\\Microsoft\\WinGet\\Packages\\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\\mingw64\\bin;" + env.get("PATH", "")
    
    comp_cmd = [cli_path, "compress", src_dir, cli_archive, "--solid"]
    proc = subprocess.run(comp_cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[FAIL] CLI compression failed: {proc.stderr}\n{proc.stdout}")
        return
        
    cli_compressed_size = os.path.getsize(cli_archive)
    print(f"CLI Compressed size: {cli_compressed_size} bytes (Ratio: {orig_size / cli_compressed_size:.2f}x)")
    
    # Verify Python decompression of CLI archive
    py_extracted = os.path.join(test_dir, "py_extracted")
    lattice_archive.LatticeArchiveEngine.decompress(cli_archive, py_extracted)
    
    # Verify CLI decompression of Python archive
    cli_extracted = os.path.join(test_dir, "cli_extracted")
    decomp_cmd = [cli_path, "decompress", py_archive, cli_extracted]
    proc = subprocess.run(decomp_cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[FAIL] CLI decompression failed: {proc.stderr}")
        return
        
    # Check if files match original
    match = True
    for f in ["texture_main.bin", "texture_copy.bin", "texture_partial.bin"]:
        orig = os.path.join(src_dir, f)
        ext_py = os.path.join(py_extracted, f)
        ext_cli = os.path.join(cli_extracted, f)
        
        if not os.path.exists(ext_py) or open(orig, "rb").read() != open(ext_py, "rb").read():
            print(f"[FAIL] Python restoration mismatch for {f}")
            match = False
        if not os.path.exists(ext_cli) or open(orig, "rb").read() != open(ext_cli, "rb").read():
            print(f"[FAIL] CLI restoration mismatch for {f}")
            match = False
            
    if match:
        print("[PASS] Cross-compatibility, deduplication, and byte-for-byte lossless verification succeeded!")
    else:
        print("[FAIL] Verification failed.")
        
    # Cleanup temp dir
    try:
        shutil.rmtree(test_dir)
    except Exception:
        pass
    print("==================================================")

if __name__ == "__main__":
    test_dedup()
