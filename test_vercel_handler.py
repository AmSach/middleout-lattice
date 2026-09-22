"""
Middleout-Lattice: Vercel Serverless Function Verification Suite
Tests the exact api/index.py serverless handler in an isolated environment.
"""

import os
import sys
import json
import base64
import hashlib
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer
from socketserver import ThreadingMixIn

# Add api directory to sys.path
REPO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_DIR / "api"))
sys.path.insert(0, str(REPO_DIR))

import index as vercel_api


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def test_vercel_serverless():
    print("============================================================")
    print("  VERCEL SERVERLESS HANDLER LOCAL SIMULATION TEST")
    print("============================================================")

    port = 8991
    server = ThreadingServer(("", port), vercel_api.handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)

    base_url = f"http://localhost:{port}"

    try:
        # 1. Test /api/status
        print("\n--- [Test 1] Vercel /api/status Endpoint ---")
        req = urllib.request.Request(f"{base_url}/api/status")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert "Vercel" in data.get("environment", "")
            print(f"  [+] Environment: {data['environment']}")
            print(f"  [+] Status: {data['status']} (Algorithm Protection: {data['algorithm_protection']})")

        # 2. Test /api/benchmarks
        print("\n--- [Test 2] Vercel /api/benchmarks Endpoint ---")
        req = urllib.request.Request(f"{base_url}/api/benchmarks")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert len(data["datasets"]) >= 4
            print(f"  [+] Verified Datasets Available: {len(data['datasets'])} (PASS)")

        # 3. Test /api/entropy
        print("\n--- [Test 3] Vercel /api/entropy Endpoint ---")
        payload = json.dumps({"text": "PROPRIETARY_ENTERPRISE_LATTICE_MODEL_DATA_STREAM\n" * 20}).encode()
        req = urllib.request.Request(f"{base_url}/api/entropy", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            print(f"  [+] Shannon Entropy: {data['entropy_bits_per_byte']} bits/byte (PASS)")

        # 4. Test /api/compress (with AES-256-GCM pilot data encryption)
        print("\n--- [Test 4] Vercel /api/compress with AES-256-GCM Encryption ---")
        sample_text = "MIDDLEOUT_LATTICE_CLOUD_VERCEL_PAYLOAD_2026\n" * 40
        orig_sha256 = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()
        pilot_secret = "CloudPilotToken#9988"

        comp_payload = json.dumps({
            "filename": "cloud_confidential.txt",
            "content_text": sample_text,
            "encrypt": True,
            "passphrase": pilot_secret,
            "solid": True
        }).encode()

        req = urllib.request.Request(f"{base_url}/api/compress", data=comp_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            comp_res = json.loads(resp.read().decode())
            assert comp_res["is_encrypted"] is True
            assert comp_res["filename"].endswith(".lat.enc")
            encrypted_b64 = comp_res["file_bytes_base64"]
            metrics = comp_res["metrics"]
            print(f"  [+] Compressed {metrics['original_size']} B -> {metrics['compressed_size']} B ({metrics['ratio']}x ratio, {metrics['space_saved_percent']}% saved)")
            print(f"  [+] Output Container: {comp_res['filename']} (AES-256-GCM AEAD Sealed)")

        # 5. Test /api/decompress wrong password rejection
        print("\n--- [Test 5] Vercel /api/decompress Wrong Password Rejection ---")
        wrong_decomp_payload = json.dumps({
            "filename": comp_res["filename"],
            "archive_base64": encrypted_b64,
            "passphrase": "InvalidPassword123"
        }).encode()
        req = urllib.request.Request(f"{base_url}/api/decompress", data=wrong_decomp_payload, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
            assert False, "Security breach: Decryption succeeded with wrong passphrase!"
        except urllib.error.HTTPError as he:
            assert he.code == 403
            print(f"  [+] Wrong Passphrase Rejection (HTTP 403 Forbidden): PASS")

        # 6. Test /api/decompress valid password extraction
        print("\n--- [Test 6] Vercel /api/decompress Valid Password Roundtrip ---")
        correct_decomp_payload = json.dumps({
            "filename": comp_res["filename"],
            "archive_base64": encrypted_b64,
            "passphrase": pilot_secret
        }).encode()
        req = urllib.request.Request(f"{base_url}/api/decompress", data=correct_decomp_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            decomp_res = json.loads(resp.read().decode())
            assert decomp_res["success"] is True
            assert decomp_res["was_encrypted"] is True
            extracted = decomp_res["files"][0]
            restored_bytes = base64.b64decode(extracted["content_base64"])
            restored_sha256 = hashlib.sha256(restored_bytes).hexdigest()
            assert restored_sha256 == orig_sha256, f"Checksum mismatch! Orig: {orig_sha256}, Restored: {restored_sha256}"
            print(f"  [+] Restored file: {extracted['path']} ({extracted['size']} B)")
            print(f"  [+] 100% Bit-Exact SHA-256 Match: {restored_sha256} (PASS)")

        print("\n============================================================")
        print("  ALL VERCEL SERVERLESS HANDLER TESTS PASSED!")
        print("============================================================")

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_vercel_serverless()
