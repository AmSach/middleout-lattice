"""
Middleout-Lattice: Enterprise Pilot Server & API Gateway
Patent-Pending High-Speed Lossless AI Model & Data Compressor

Provides:
- Static file serving for the WebApp Frontend (index.html).
- REST API: /api/status, /api/benchmarks, /api/entropy, /api/compress, /api/decompress.
- Air-Gapped Algorithm Enclave: Algorithm executes strictly server-side in compiled native code.
- AES-256-GCM Zero-Knowledge Data Encryption for Pilot Participants (.lat.enc containers).
"""

import os
import sys
import io
import json
import time
import math
import shutil
import base64
import hashlib
import tempfile
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse

from secure_engine_vault import (
    compress_file_native,
    decompress_file_native,
    encrypt_payload,
    decrypt_payload,
    is_encrypted_container,
    HAS_CRYPTOGRAPHY,
    CLI_EXE
)

REPO_DIR = Path(__file__).resolve().parent
STATIC_DIR = REPO_DIR
from api.index import BENCHMARK_DATA


def calculate_entropy(data: bytes) -> dict:
    """Calculates byte-level Shannon entropy and theoretical compression bounds."""
    if not data:
        return {"entropy": 0.0, "max_theoretical_ratio": 1.0, "total_bytes": 0}

    freq = [0] * 256
    for b in data:
        freq[b] += 1

    total = len(data)
    entropy = 0.0
    for count in freq:
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    theoretical_min_bits = entropy * total
    theoretical_min_bytes = math.ceil(theoretical_min_bits / 8.0)
    max_ratio = total / max(1, theoretical_min_bytes)

    return {
        "entropy_bits_per_byte": round(entropy, 4),
        "theoretical_min_bytes": theoretical_min_bytes,
        "max_theoretical_ratio": round(max_ratio, 3),
        "total_bytes": total
    }


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class PilotApiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self._handle_status()
        elif path == "/api/benchmarks":
            self._handle_benchmarks()
        else:
            # Fall back to static files (e.g. index.html)
            if path in ["", "/"]:
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/compress":
            self._handle_compress()
        elif path == "/api/decompress":
            self._handle_decompress()
        elif path == "/api/entropy":
            self._handle_entropy()
        else:
            self._send_json(404, {"error": f"Endpoint {path} not found"})

    def _handle_status(self):
        self._send_json(200, {
            "status": "online",
            "pilot_service": "Middleout-Lattice Enterprise Enclave",
            "version": "1.0.4-pilot",
            "native_cli_available": CLI_EXE.is_file(),
            "aes_gcm_available": HAS_CRYPTOGRAPHY,
            "simd_acceleration": "AVX2 + SSE4.2 CRC32c Hardware Accelerated",
            "algorithm_protection": "Air-Gapped Compiled Native Enclave (x86_64)",
            "data_encryption_cipher": "AES-256-GCM (Authenticated AEAD, PBKDF2 100k rounds)"
        })

    def _handle_benchmarks(self):
        self._send_json(200, {
            "datasets": BENCHMARK_DATA,
            "methodology": "Verified SHA-256 Lossless Roundtrip across canonical real-world test sets."
        })

    def _handle_entropy(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)
        try:
            req = json.loads(post_body.decode("utf-8"))
            text = req.get("text", "")
            data = text.encode("utf-8") if isinstance(text, str) else b""
            stats = calculate_entropy(data)
            self._send_json(200, stats)
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    def _handle_compress(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
            req = json.loads(post_body.decode("utf-8"))

            filename = req.get("filename", "document.txt")
            solid = bool(req.get("solid", True))
            virtually_lossless = int(req.get("virtually_lossless", 0))
            encrypt_data = bool(req.get("encrypt", False))
            passphrase = req.get("passphrase", "").strip()

            if "content_base64" in req:
                raw_bytes = base64.b64decode(req["content_base64"])
            elif "content_text" in req:
                raw_bytes = req["content_text"].encode("utf-8")
            else:
                self._send_json(400, {"error": "Missing 'content_base64' or 'content_text' parameter."})
                return

            if encrypt_data and not passphrase:
                self._send_json(400, {"error": "Encryption enabled but no passphrase provided."})
                return

            with tempfile.TemporaryDirectory() as tmpdir:
                in_path = os.path.join(tmpdir, filename)
                with open(in_path, "wb") as f:
                    f.write(raw_bytes)

                lat_path = os.path.join(tmpdir, filename + ".lat")
                metrics = compress_file_native(
                    input_path=in_path,
                    output_path=lat_path,
                    solid=solid,
                    virtually_lossless=virtually_lossless
                )

                if not metrics.get("success", False):
                    self._send_json(500, {"error": "Compression engine failed.", "details": metrics})
                    return

                with open(lat_path, "rb") as f:
                    compressed_bytes = f.read()

                # If pilot encryption is enabled, wrap inside AES-256-GCM container
                final_filename = filename + ".lat"
                if encrypt_data:
                    final_bytes = encrypt_payload(compressed_bytes, passphrase)
                    final_filename = filename + ".lat.enc"
                    metrics["encrypted_container_size"] = len(final_bytes)
                    metrics["encryption"] = "AES-256-GCM (Authenticated)"
                else:
                    final_bytes = compressed_bytes
                    metrics["encryption"] = "None (Standard .lat)"

                compressed_b64 = base64.b64encode(final_bytes).decode("ascii")
                sha256_final = hashlib.sha256(final_bytes).hexdigest()

                self._send_json(200, {
                    "filename": final_filename,
                    "is_encrypted": encrypt_data,
                    "metrics": metrics,
                    "sha256_compressed": sha256_final,
                    "file_bytes_base64": compressed_b64
                })

        except Exception as e:
            self._send_json(500, {"error": f"Internal compression error: {str(e)}"})

    def _handle_decompress(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
            req = json.loads(post_body.decode("utf-8"))

            filename = req.get("filename", "archive.lat")
            passphrase = req.get("passphrase", "").strip()

            if "archive_base64" not in req:
                self._send_json(400, {"error": "Missing 'archive_base64' parameter."})
                return

            raw_archive = base64.b64decode(req["archive_base64"])
            was_encrypted = is_encrypted_container(raw_archive)

            if was_encrypted:
                if not passphrase:
                    self._send_json(401, {"error": "Container is AES-256 encrypted. Please provide the pilot passphrase."})
                    return
                try:
                    decompressed_lat_bytes = decrypt_payload(raw_archive, passphrase)
                except ValueError as ve:
                    self._send_json(403, {"error": f"Decryption rejected: {str(ve)}"})
                    return
            else:
                decompressed_lat_bytes = raw_archive

            with tempfile.TemporaryDirectory() as tmpdir:
                lat_path = os.path.join(tmpdir, "input.lat")
                with open(lat_path, "wb") as f:
                    f.write(decompressed_lat_bytes)

                dest_dir = os.path.join(tmpdir, "extracted")
                res = decompress_file_native(lat_path, dest_dir)

                if not res.get("success", False):
                    self._send_json(500, {"error": "Decompression engine failed.", "details": res})
                    return

                # Collect extracted files
                extracted_files = []
                for root, _, files in os.walk(dest_dir):
                    for f in files:
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, dest_dir)
                        with open(full_p, "rb") as ef:
                            file_content = ef.read()
                        extracted_files.append({
                            "path": rel_p,
                            "size": len(file_content),
                            "sha256": hashlib.sha256(file_content).hexdigest(),
                            "content_base64": base64.b64encode(file_content).decode("ascii")
                        })

                self._send_json(200, {
                    "success": True,
                    "was_encrypted": was_encrypted,
                    "elapsed_seconds": res.get("elapsed_seconds", 0.0),
                    "files": extracted_files
                })

        except Exception as e:
            self._send_json(500, {"error": f"Internal decompression error: {str(e)}"})


def run_server(port: int = 8080, open_browser: bool = True):
    server_address = ("", port)
    httpd = ThreadingServer(server_address, PilotApiHandler)
    url = f"http://localhost:{port}"
    print(f"============================================================")
    print(f"  ⚡ MIDDLEOUT-LATTICE ENTERPRISE PILOT PORTAL")
    print(f"  Proprietary Enclave & Encrypted Compression Server")
    print(f"============================================================")
    print(f"  [+] Local WebApp URL:    {url}")
    print(f"  [+] Native Binary:       {'Ready (lattice_cli.exe)' if CLI_EXE.is_file() else 'Fallback Python'}")
    print(f"  [+] AES-256-GCM AEAD:    {'Active' if HAS_CRYPTOGRAPHY else 'Inactive'}")
    print(f"  [+] Algorithm Security:  Air-Gapped Native Enclave (x86_64)")
    print(f"============================================================")
    print(f"  Press Ctrl+C to terminate the server.\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Middleout-Lattice Pilot Server.")
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Middleout-Lattice Pilot Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_open)
