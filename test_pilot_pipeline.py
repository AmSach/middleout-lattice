"""
Middleout-Lattice: Automated Test Suite for Pilot WebApp, API, & Encryption Enclave
Tests:
1. AES-256-GCM authenticated encryption/decryption roundtrips.
2. Tamper and wrong-passphrase rejection.
3. Native engine compression (.lat).
4. Pilot encrypted container compression (.lat.enc).
5. Lossless SHA-256 bit-exact roundtrip verification.
6. API endpoints: /api/status, /api/benchmarks, /api/entropy, /api/compress, /api/decompress.
7. Algorithm Vault encryption and locking.
"""

import os
import sys
import json
import base64
import hashlib
import tempfile
import threading
import time
import urllib.request
import urllib.error

from secure_engine_vault import (
    encrypt_payload,
    decrypt_payload,
    is_encrypted_container,
    compress_file_native,
    decompress_file_native,
    lock_algorithm_vault
)
from pilot_server import ThreadingServer, PilotApiHandler


def test_encryption_primitives():
    print("\n--- [Test 1] Testing AES-256-GCM Authenticated Encryption ---")
    secret_pass = "QuantumPilotPassphrase2026!#"
    test_data = b"CONFIDENTIAL PILOT DATA: Proprietary neural weights & financial records." * 50

    encrypted = encrypt_payload(test_data, secret_pass)
    assert is_encrypted_container(encrypted), "Failed to detect encrypted container magic bytes!"
    print(f"  [+] Plaintext size: {len(test_data)} B -> Encrypted container: {len(encrypted)} B")

    decrypted = decrypt_payload(encrypted, secret_pass)
    assert decrypted == test_data, "Decrypted data does not match original plaintext!"
    print("  [+] Decryption with valid passphrase: PASS (Bit-Exact)")

    # Test rejection with invalid passphrase
    rejected = False
    try:
        decrypt_payload(encrypted, "WrongPassword123")
    except ValueError:
        rejected = True
    assert rejected, "Security failure: Decrypt succeeded with wrong password!"
    print("  [+] Invalid passphrase rejection: PASS (Cryptographic Auth Tag Enforced)")

    # Test tampering rejection
    tampered = bytearray(encrypted)
    tampered[-5] ^= 0xFF  # Flip bits in ciphertext/tag
    rejected_tamper = False
    try:
        decrypt_payload(bytes(tampered), secret_pass)
    except ValueError:
        rejected_tamper = True
    assert rejected_tamper, "Security failure: Decrypt succeeded on tampered payload!"
    print("  [+] Tamper detection & AEAD tag rejection: PASS")


def test_native_compression_and_decompression():
    print("\n--- [Test 2] Testing Native Compression & Roundtrip ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = os.path.join(tmpdir, "sample.txt")
        test_content = ("Middleout-Lattice Patent-Pending Lossless AI Compressor.\n" * 200).encode("utf-8")
        with open(input_file, "wb") as f:
            f.write(test_content)

        orig_sha256 = hashlib.sha256(test_content).hexdigest()
        lat_file = os.path.join(tmpdir, "sample.txt.lat")

        metrics = compress_file_native(input_file, lat_file, solid=True)
        assert metrics["success"], f"Compression failed: {metrics}"
        print(f"  [+] Original Size: {metrics['original_size']} B -> Compressed: {metrics['compressed_size']} B")
        print(f"  [+] Compression Ratio: {metrics['ratio']}x ({metrics['space_saved_percent']}% saved)")
        print(f"  [+] Execution Time: {metrics['elapsed_seconds']}s ({metrics['throughput_mbps']} MB/s)")

        # Test native decompress
        dest_dir = os.path.join(tmpdir, "extracted")
        decomp_res = decompress_file_native(lat_file, dest_dir)
        assert decomp_res["success"], "Decompression failed!"

        extracted_file = os.path.join(dest_dir, "sample.txt")
        assert os.path.exists(extracted_file), "Extracted file missing!"
        decomp_content = open(extracted_file, "rb").read()
        decomp_sha256 = hashlib.sha256(decomp_content).hexdigest()

        assert orig_sha256 == decomp_sha256, f"SHA-256 mismatch! Orig: {orig_sha256}, Decomp: {decomp_sha256}"
        print(f"  [+] 100% Bit-Exact SHA-256 Match: {decomp_sha256} (PASS)")


def test_api_endpoints():
    print("\n--- [Test 3] Testing Pilot Server REST API Endpoints ---")
    port = 8899
    server = ThreadingServer(("", port), PilotApiHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    base_url = f"http://localhost:{port}"

    try:
        # 1. GET /api/status
        req = urllib.request.Request(f"{base_url}/api/status")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["status"] == "online"
            print(f"  [+] GET /api/status: PASS (Enclave: {data['algorithm_protection']})")

        # 2. GET /api/benchmarks
        req = urllib.request.Request(f"{base_url}/api/benchmarks")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert len(data["datasets"]) >= 4
            print(f"  [+] GET /api/benchmarks: PASS ({len(data['datasets'])} datasets loaded)")

        # 3. POST /api/entropy
        payload = json.dumps({"text": "AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRSSTTUUVVWWXXYYZZ"}).encode()
        req = urllib.request.Request(f"{base_url}/api/entropy", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["entropy_bits_per_byte"] > 0
            print(f"  [+] POST /api/entropy: PASS (Entropy: {data['entropy_bits_per_byte']} bits/byte)")

        # 4. POST /api/compress (with pilot encryption)
        raw_text = "MIDDLEOUT_SECRET_TOKEN_2026_TEST_FILE_CONTENT\n" * 50
        orig_sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        pilot_pass = "EnterpriseShieldKey#99"

        comp_payload = json.dumps({
            "filename": "confidential_spec.txt",
            "content_text": raw_text,
            "encrypt": True,
            "passphrase": pilot_pass,
            "solid": True
        }).encode()

        req = urllib.request.Request(f"{base_url}/api/compress", data=comp_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            comp_res = json.loads(resp.read().decode())
            assert comp_res["is_encrypted"] is True
            assert comp_res["filename"].endswith(".lat.enc")
            encrypted_b64 = comp_res["file_bytes_base64"]
            print(f"  [+] POST /api/compress (Encrypted .lat.enc): PASS ({comp_res['metrics']['ratio']}x ratio)")

        # 5. POST /api/decompress (with wrong password -> expect 403)
        wrong_decomp_payload = json.dumps({
            "filename": comp_res["filename"],
            "archive_base64": encrypted_b64,
            "passphrase": "WrongPassword!"
        }).encode()
        req = urllib.request.Request(f"{base_url}/api/decompress", data=wrong_decomp_payload, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
            assert False, "Expected 403 on wrong password!"
        except urllib.error.HTTPError as he:
            assert he.code == 403
            print("  [+] POST /api/decompress (Wrong Password -> 403 Forbidden): PASS")

        # 6. POST /api/decompress (with correct password)
        correct_decomp_payload = json.dumps({
            "filename": comp_res["filename"],
            "archive_base64": encrypted_b64,
            "passphrase": pilot_pass
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
            assert restored_sha256 == orig_sha256, "Restored content does not match original!"
            print(f"  [+] POST /api/decompress (Correct Password -> 100% SHA-256 Match): PASS")

        # 7. GET / (index.html frontend serving)
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            html = resp.read().decode()
            assert "MIDDLEOUT-LATTICE" in html
            assert "Industrial Showcase" in html
            print("  [+] GET / (index.html WebApp Delivery): PASS")

    finally:
        server.shutdown()
        server.server_close()


def test_algorithm_vault_lock():
    print("\n--- [Test 4] Testing Proprietary Algorithm Vault Locking ---")
    vault_file = "test_engine.vault"
    try:
        size = lock_algorithm_vault("SecretVaultKey2026", vault_file)
        assert os.path.exists(vault_file), "Vault file not generated!"
        assert size > 0, "Vault file is empty!"
        print(f"  [+] Proprietary Python engine encrypted into {vault_file} ({size} B): PASS")
    finally:
        if os.path.exists(vault_file):
            os.remove(vault_file)


if __name__ == "__main__":
    print("============================================================")
    print("  MIDDLEOUT-LATTICE PILOT & ENCLAVE TEST SUITE")
    print("============================================================")
    test_encryption_primitives()
    test_native_compression_and_decompression()
    test_api_endpoints()
    test_algorithm_vault_lock()
    print("\n============================================================")
    print("  ALL TESTS PASSED WITH 100% BIT-EXACT INTEGRITY!")
    print("============================================================")
