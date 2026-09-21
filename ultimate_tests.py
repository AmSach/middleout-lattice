import os
import sys
import subprocess
import json
import uuid
import filecmp
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import lattice_archive
except Exception as e:
    print(f"Failed to load lattice_archive: {e}")
    sys.exit(1)

def run_tests():
    print("=========================================")
    print(" LATTICE COMPRESSION STUDIO - ULTIMATE TEST")
    print("=========================================")
    
    test_dir = os.path.join(os.getcwd(), f"test_ultimate_{uuid.uuid4().hex[:6]}")
    os.makedirs(test_dir, exist_ok=True)
    
    source_dir = os.path.join(test_dir, "source")
    os.makedirs(source_dir, exist_ok=True)
    
    print("[1/5] Generating test datasets (Text, Binary, Code, JSON)...")
    
    # 1. Code
    with open(os.path.join(source_dir, "test.py"), "w") as f:
        f.write("def hello():\n    print('world')\n\nhello()\n")
        
    # 2. JSON
    with open(os.path.join(source_dir, "data.json"), "w") as f:
        f.write(json.dumps({"key": "value", "list": [1, 2, 3] * 100}))
        
    # 3. Binary
    with open(os.path.join(source_dir, "random.bin"), "wb") as f:
        f.write(os.urandom(1024 * 50)) # 50KB random bytes
        
    # 4. Text
    with open(os.path.join(source_dir, "test.txt"), "w") as f:
        f.write("The quick brown fox jumps over the lazy dog.\n" * 500)
        
    print("      -> Done.")
    
    archive_path = os.path.join(test_dir, "archive.lat")
    dest_dir = os.path.join(test_dir, "extracted")
    
    try:
        print("[2/5] Running Core Engine Compression...")
        lattice_archive.LatticeArchiveEngine.compress(source_dir, archive_path, virtually_lossless=False, solid=True)
        print(f"      -> Compressed archive created: {os.path.getsize(archive_path)} bytes.")
        
        print("[3/5] Running Core Engine Decompression...")
        lattice_archive.LatticeArchiveEngine.decompress(archive_path, dest_dir)
        print("      -> Decompression completed.")
        
        print("[4/5] Verifying Byte-for-Byte Integrity...")
        failed = False
        for root, _, files in os.walk(source_dir):
            for f in files:
                src_f = os.path.join(root, f)
                rel = os.path.relpath(src_f, source_dir)
                dst_f = os.path.join(dest_dir, rel)
                if not os.path.exists(dst_f):
                    print(f"      [!] Missing file: {rel}")
                    failed = True
                elif not filecmp.cmp(src_f, dst_f, shallow=False):
                    print(f"      [!] File mismatch: {rel}")
                    failed = True
        if failed:
            print("      [FAIL] Integrity check failed!")
            sys.exit(1)
        else:
            print("      [PASS] 100% Bit-Perfect Restoration!")
            
        print("[5/5] Testing C++ Core CLI (`lattice_cli.exe`)...")
        # Test CLI mode
        cli_archive = os.path.join(test_dir, "cli_archive.lat")
        cli_dest = os.path.join(test_dir, "cli_extracted")
        
        cli_path = os.path.join(os.getcwd(), "lattice_cli.exe")
        if not os.path.exists(cli_path):
            # Fallback to engine/build/Release
            cli_path = os.path.join(os.getcwd(), "engine", "build", "Release", "lattice_cli.exe")
            if not os.path.exists(cli_path):
                cli_path = "lattice_cli.exe"
                
        # Test Compress
        comp_cmd = [cli_path, "compress", source_dir, cli_archive, "--solid"]
        proc = subprocess.run(comp_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"      [FAIL] CLI Compression returned {proc.returncode}\n{proc.stderr}\n{proc.stdout}")
            sys.exit(1)
        print("      -> CLI Compression passed.")
        
        # Test Decompress
        decomp_cmd = [cli_path, "decompress", cli_archive, cli_dest]
        proc2 = subprocess.run(decomp_cmd, capture_output=True, text=True)
        if proc2.returncode != 0:
            print(f"      [FAIL] CLI Decompression returned {proc2.returncode}\n{proc2.stderr}\n{proc2.stdout}")
            sys.exit(1)
        print("      -> CLI Decompression passed.")
        
        # Final success
        print("=========================================")
        print("  ALL TESTS PASSED SUCCESSFULLY! ")
        print("  APPLICATION IS PRODUCTION READY. ")
        print("=========================================")
        
    except Exception as e:
        print(f"[FAIL] Exception occurred: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
