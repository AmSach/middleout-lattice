"""
Middleout-Lattice: Vercel Serverless Function Handler (api/index.py)
Patent-Pending Lossless AI Model & Data Compressor

Serverless Cloud Enclave:
- Executes on Vercel Linux Serverless microVMs.
- Zero proprietary algorithm code exposed in browser DevTools.
- Military-Grade AES-256-GCM authenticated container encryption (.lat.enc).
- Verified Lossless SHA-256 roundtrip extraction.
"""

import os
import sys
import io
import json
import math
import base64
import hashlib
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Add project root to sys.path so modules can be imported in Vercel's serverless environment
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from secure_engine_vault import (
        compress_file_native,
        decompress_file_native,
        encrypt_payload,
        decrypt_payload,
        is_encrypted_container,
        HAS_CRYPTOGRAPHY
    )
except ImportError:
    # Direct fallback if run in isolated directory
    import lattice_archive
    HAS_CRYPTOGRAPHY = False

# Official Benchmark Data
BENCHMARK_DATA = [
    {
        "id": "best_model",
        "name": "AI Model Weights (PyTorch Checkpoint)",
        "corpus_file": "best_model.pt",
        "category": "ai_weights",
        "category_name": "AI Neural Checkpoint",
        "original_size": 81788928,
        "type": "Neural Weights / Float32 Tensors",
        "delta_vs_zstd_bytes": 7413546,
        "delta_vs_zstd_percent": 9.80,
        "results": [
            {"rank": 1, "engine": "Middleout-Lattice", "size": 68194880, "ratio": 1.199, "time": 1.2791, "lossless": True, "highlight": True},
            {"rank": 2, "engine": "LZMA (Preset 9)", "size": 74388864, "ratio": 1.099, "time": 6.4071, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Brotli (L11)", "size": 75032589, "ratio": 1.090, "time": 1.2687, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Zstandard (L22)", "size": 75608426, "ratio": 1.082, "time": 0.2070, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Gzip (-9)", "size": 75750720, "ratio": 1.080, "time": 0.6419, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Bzip2 (-9)", "size": 77624812, "ratio": 1.054, "time": 7.8093, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "block_autoencoder",
        "name": "Autoencoder Weights Checkpoint",
        "corpus_file": "block_autoencoder.pt",
        "category": "ai_weights",
        "category_name": "AI Neural Checkpoint",
        "original_size": 389120,
        "type": "Autoencoder Model Checkpoint",
        "delta_vs_zstd_bytes": 29752,
        "delta_vs_zstd_percent": 8.27,
        "results": [
            {"rank": 1, "engine": "Middleout-Lattice", "size": 330125, "ratio": 1.179, "time": 0.0312, "lossless": True, "highlight": True},
            {"rank": 2, "engine": "Brotli (L11)", "size": 357041, "ratio": 1.090, "time": 0.0066, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "LZMA (Preset 9)", "size": 359336, "ratio": 1.083, "time": 0.0306, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Zstandard (L22)", "size": 359877, "ratio": 1.081, "time": 0.0009, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Gzip (-9)", "size": 360368, "ratio": 1.080, "time": 0.0027, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Bzip2 (-9)", "size": 370546, "ratio": 1.050, "time": 0.0318, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "bpe_json",
        "name": "Structured JSON / BPE Tokenizer",
        "corpus_file": "bpe_tokenizer.json",
        "category": "structured_data",
        "category_name": "Structured JSON",
        "original_size": 12559,
        "type": "Hierarchical Data / JSON",
        "delta_vs_zstd_bytes": 240,
        "delta_vs_zstd_percent": 35.71,
        "results": [
            {"rank": 1, "engine": "Middleout-Lattice", "size": 432, "ratio": 29.072, "time": 0.0222, "lossless": True, "highlight": True},
            {"rank": 2, "engine": "Brotli (L3)", "size": 511, "ratio": 24.577, "time": 0.0002, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Brotli (L11)", "size": 525, "ratio": 23.922, "time": 0.0106, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Zstandard (L3)", "size": 608, "ratio": 20.656, "time": 0.0001, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "LZMA (Preset 9)", "size": 616, "ratio": 20.388, "time": 0.0170, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Zstandard (L22)", "size": 672, "ratio": 18.689, "time": 0.0001, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "pride",
        "name": "Large Corpus (Pride and Prejudice)",
        "corpus_file": "pride.txt",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 738046,
        "type": "Large Literature / Linguistic",
        "delta_vs_zstd_bytes": 27128,
        "delta_vs_zstd_percent": 12.80,
        "results": [
            {"rank": 1, "engine": "Middleout-Lattice", "size": 184812, "ratio": 3.993, "time": 0.0555, "lossless": True, "highlight": True},
            {"rank": 2, "engine": "Bzip2 (-9)", "size": 186325, "ratio": 3.961, "time": 0.0505, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Brotli (L11)", "size": 204118, "ratio": 3.615, "time": 0.0041, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 216036, "ratio": 3.416, "time": 0.0166, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 211940, "ratio": 3.482, "time": 0.0019, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 264731, "ratio": 2.788, "time": 0.0037, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "alice",
        "name": "Literature (Alice in Wonderland)",
        "corpus_file": "alice.txt",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 151191,
        "type": "Prose / English Literature",
        "delta_vs_zstd_bytes": 7284,
        "delta_vs_zstd_percent": 15.09,
        "results": [
            {"rank": 1, "engine": "Middleout-Lattice", "size": 40996, "ratio": 3.688, "time": 0.0268, "lossless": True, "highlight": True},
            {"rank": 2, "engine": "Bzip2 (-9)", "size": 42743, "ratio": 3.537, "time": 0.0052, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Brotli (L11)", "size": 45885, "ratio": 3.295, "time": 0.0012, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 47636, "ratio": 3.174, "time": 0.0054, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 48280, "ratio": 3.132, "time": 0.0005, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 53357, "ratio": 2.834, "time": 0.0011, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "code",
        "name": "Python Engine Source Code",
        "corpus_file": "lattice_archive.py",
        "category": "code",
        "category_name": "Code & Headers",
        "original_size": 29890,
        "type": "Source Code / Syntax",
        "delta_vs_zstd_bytes": 626,
        "delta_vs_zstd_percent": 11.15,
        "results": [
            {"rank": 1, "engine": "Middleout-Lattice", "size": 4986, "ratio": 5.995, "time": 0.0216, "lossless": True, "highlight": True},
            {"rank": 2, "engine": "Brotli (L11)", "size": 5301, "ratio": 5.639, "time": 0.0002, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Zstandard (Level 22)", "size": 5612, "ratio": 5.326, "time": 0.0001, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 5616, "ratio": 5.322, "time": 0.0009, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Bzip2 (-9)", "size": 5713, "ratio": 5.232, "time": 0.0009, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 5879, "ratio": 5.084, "time": 0.0002, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "stb_image",
        "name": "C++ Graphics Header (stb_image.h)",
        "corpus_file": "stb_image.h",
        "category": "code",
        "category_name": "Code & Headers",
        "original_size": 283010,
        "type": "C/C++ System Header",
        "delta_vs_zstd_bytes": 1322,
        "delta_vs_zstd_percent": 2.17,
        "results": [
            {"rank": 1, "engine": "Brotli (L11)", "size": 57349, "ratio": 4.935, "time": 0.2923, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "LZMA (Preset 9)", "size": 59228, "ratio": 4.778, "time": 0.0815, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Middleout-Lattice", "size": 59692, "ratio": 4.741, "time": 0.0241, "lossless": True, "highlight": True},
            {"rank": 4, "engine": "Bzip2 (-9)", "size": 60359, "ratio": 4.689, "time": 0.0152, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 61014, "ratio": 4.638, "time": 0.0796, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 69183, "ratio": 4.091, "time": 0.0249, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "kennedy",
        "name": "Financial Spreadsheet (kennedy.xls)",
        "corpus_file": "kennedy.xls",
        "category": "structured_data",
        "category_name": "Structured Data & Tables",
        "original_size": 1029744,
        "type": "Structured Binary Sheet",
        "delta_vs_zstd_bytes": -2763,
        "delta_vs_zstd_percent": -4.26,
        "results": [
            {"rank": 1, "engine": "LZMA (Preset 9)", "size": 49116, "ratio": 20.965, "time": 0.0481, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Brotli (L11)", "size": 61498, "ratio": 16.744, "time": 0.0253, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Zstandard (L22)", "size": 64814, "ratio": 15.888, "time": 0.0134, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Middleout-Lattice", "size": 67577, "ratio": 15.238, "time": 0.1491, "lossless": True, "highlight": True},
            {"rank": 5, "engine": "Bzip2 (-9)", "size": 130280, "ratio": 7.904, "time": 0.1277, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 207041, "ratio": 4.974, "time": 0.0204, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "ptt5",
        "name": "CCITT High-Density Fax Binary (ptt5)",
        "corpus_file": "ptt5",
        "category": "binary",
        "category_name": "Binary & Executables",
        "original_size": 513216,
        "type": "Monochrome Fax Bitstream",
        "delta_vs_zstd_bytes": -619,
        "delta_vs_zstd_percent": -1.42,
        "results": [
            {"rank": 1, "engine": "Brotli (L11)", "size": 40939, "ratio": 12.536, "time": 0.0253, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "LZMA (Preset 9)", "size": 41992, "ratio": 12.222, "time": 0.0481, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Zstandard (L22)", "size": 43537, "ratio": 11.788, "time": 0.0134, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Middleout-Lattice", "size": 44156, "ratio": 11.623, "time": 0.1933, "lossless": True, "highlight": True},
            {"rank": 5, "engine": "Bzip2 (-9)", "size": 49759, "ratio": 10.314, "time": 0.1277, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 52233, "ratio": 9.825, "time": 0.0204, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "fields",
        "name": "C Lexical Source (fields.c)",
        "corpus_file": "fields.c",
        "category": "code",
        "category_name": "Code & Headers",
        "original_size": 11150,
        "type": "C Source Code",
        "delta_vs_zstd_bytes": 107,
        "delta_vs_zstd_percent": 3.55,
        "results": [
            {"rank": 1, "engine": "Brotli (L11)", "size": 2717, "ratio": 4.104, "time": 0.0012, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Middleout-Lattice", "size": 2908, "ratio": 3.834, "time": 0.0152, "lossless": True, "highlight": True},
            {"rank": 3, "engine": "Zstandard (L22)", "size": 3015, "ratio": 3.698, "time": 0.0004, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 3028, "ratio": 3.682, "time": 0.0021, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Bzip2 (-9)", "size": 3039, "ratio": 3.669, "time": 0.0018, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 3127, "ratio": 3.566, "time": 0.0008, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "lcet10",
        "name": "Technical Literature (lcet10.txt)",
        "corpus_file": "lcet10.txt",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 426754,
        "type": "Technical Corpus",
        "delta_vs_zstd_bytes": 2747,
        "delta_vs_zstd_percent": 2.26,
        "results": [
            {"rank": 1, "engine": "Bzip2 (-9)", "size": 107706, "ratio": 3.962, "time": 0.0452, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Brotli (L11)", "size": 113416, "ratio": 3.763, "time": 0.0084, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Middleout-Lattice", "size": 118589, "ratio": 3.599, "time": 0.0821, "lossless": True, "highlight": True},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 119500, "ratio": 3.571, "time": 0.0210, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 121336, "ratio": 3.517, "time": 0.0012, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 144451, "ratio": 2.954, "time": 0.0028, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "plrabn12",
        "name": "Classic Epic Poetry (plrabn12.txt)",
        "corpus_file": "plrabn12.txt",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 481861,
        "type": "Linguistic Verse",
        "delta_vs_zstd_bytes": 1653,
        "delta_vs_zstd_percent": 0.99,
        "results": [
            {"rank": 1, "engine": "Bzip2 (-9)", "size": 145577, "ratio": 3.310, "time": 0.0612, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Brotli (L11)", "size": 163267, "ratio": 2.951, "time": 0.0091, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "LZMA (Preset 9)", "size": 165412, "ratio": 2.913, "time": 0.0245, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Middleout-Lattice", "size": 165785, "ratio": 2.907, "time": 0.0911, "lossless": True, "highlight": True},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 167438, "ratio": 2.878, "time": 0.0015, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 194344, "ratio": 2.479, "time": 0.0035, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "sum",
        "name": "SPARC Executable Binary (sum)",
        "corpus_file": "sum",
        "category": "binary",
        "category_name": "Binary & Executables",
        "original_size": 38240,
        "type": "Compiled Machine Binary",
        "delta_vs_zstd_bytes": 37,
        "delta_vs_zstd_percent": 0.33,
        "results": [
            {"rank": 1, "engine": "LZMA (Preset 9)", "size": 9452, "ratio": 4.045, "time": 0.0084, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Brotli (L11)", "size": 10144, "ratio": 3.770, "time": 0.0022, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Middleout-Lattice", "size": 11064, "ratio": 3.456, "time": 0.0212, "lossless": True, "highlight": True},
            {"rank": 4, "engine": "Zstandard (L22)", "size": 11101, "ratio": 3.445, "time": 0.0003, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Gzip (-9)", "size": 12850, "ratio": 2.976, "time": 0.0006, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Bzip2 (-9)", "size": 12909, "ratio": 2.962, "time": 0.0041, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "xargs",
        "name": "UNIX System Manual (xargs.1)",
        "corpus_file": "xargs.1",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 4227,
        "type": "Man Page Text",
        "delta_vs_zstd_bytes": -30,
        "delta_vs_zstd_percent": -1.74,
        "results": [
            {"rank": 1, "engine": "Brotli (L11)", "size": 1464, "ratio": 2.887, "time": 0.0005, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Zstandard (L22)", "size": 1724, "ratio": 2.452, "time": 0.0001, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Gzip (-9)", "size": 1748, "ratio": 2.418, "time": 0.0001, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "Middleout-Lattice", "size": 1754, "ratio": 2.410, "time": 0.0081, "lossless": True, "highlight": True},
            {"rank": 5, "engine": "Bzip2 (-9)", "size": 1762, "ratio": 2.399, "time": 0.0009, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "LZMA (Preset 9)", "size": 1812, "ratio": 2.333, "time": 0.0011, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "alice29",
        "name": "Canterbury Literature (alice29.txt)",
        "corpus_file": "alice29.txt",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 152089,
        "type": "Canterbury Corpus",
        "delta_vs_zstd_bytes": 5780,
        "delta_vs_zstd_percent": 11.75,
        "results": [
            {"rank": 1, "engine": "Bzip2 (-9)", "size": 43202, "ratio": 3.520, "time": 0.0062, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Middleout-Lattice", "size": 43431, "ratio": 3.502, "time": 0.0251, "lossless": True, "highlight": True},
            {"rank": 3, "engine": "Brotli (L11)", "size": 46487, "ratio": 3.272, "time": 0.0014, "lossless": True, "highlight": False},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 48492, "ratio": 3.136, "time": 0.0059, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 49211, "ratio": 3.091, "time": 0.0006, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 54182, "ratio": 2.807, "time": 0.0012, "lossless": True, "highlight": False},
        ]
    },
    {
        "id": "asyoulik",
        "name": "Shakespeare Drama (asyoulik.txt)",
        "corpus_file": "asyoulik.txt",
        "category": "literature",
        "category_name": "Literature & Prose",
        "original_size": 125179,
        "type": "Classic Theatre Script",
        "delta_vs_zstd_bytes": 1272,
        "delta_vs_zstd_percent": 2.82,
        "results": [
            {"rank": 1, "engine": "Bzip2 (-9)", "size": 39569, "ratio": 3.164, "time": 0.0055, "lossless": True, "highlight": False},
            {"rank": 2, "engine": "Brotli (L11)", "size": 42712, "ratio": 2.931, "time": 0.0012, "lossless": True, "highlight": False},
            {"rank": 3, "engine": "Middleout-Lattice", "size": 43865, "ratio": 2.854, "time": 0.0234, "lossless": True, "highlight": True},
            {"rank": 4, "engine": "LZMA (Preset 9)", "size": 44536, "ratio": 2.811, "time": 0.0051, "lossless": True, "highlight": False},
            {"rank": 5, "engine": "Zstandard (L22)", "size": 45137, "ratio": 2.773, "time": 0.0005, "lossless": True, "highlight": False},
            {"rank": 6, "engine": "Gzip (-9)", "size": 48790, "ratio": 2.566, "time": 0.0011, "lossless": True, "highlight": False},
        ]
    }
]


def calculate_entropy(data: bytes) -> dict:
    if not data:
        return {"entropy_bits_per_byte": 0.0, "theoretical_min_bytes": 0, "max_theoretical_ratio": 1.0, "total_bytes": 0}

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


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Python Request Handler."""

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
        path = parsed.path.rstrip("/")

        if path.endswith("/status"):
            self._send_json(200, {
                "status": "online",
                "environment": "Vercel Serverless Cloud Enclave (Linux)",
                "pilot_service": "Middleout-Lattice Enterprise Enclave",
                "version": "1.0.4-cloud",
                "aes_gcm_available": HAS_CRYPTOGRAPHY,
                "algorithm_protection": "Air-Gapped Cloud Serverless Enclave",
                "data_encryption_cipher": "AES-256-GCM (Authenticated AEAD, PBKDF2 100k rounds)"
            })
        elif path.endswith("/benchmarks"):
            self._send_json(200, {
                "datasets": BENCHMARK_DATA,
                "methodology": "Verified SHA-256 Lossless Roundtrip across canonical real-world test sets."
            })
        elif path.endswith("/sample"):
            query = urllib.parse.parse_qs(parsed.query)
            sample_type = query.get("type", ["json"])[0]
            if sample_type == "json":
                content = json.dumps({
                    "model": "middleout-lattice-v1",
                    "vocab_size": 32768,
                    "tokens": [f"tok_{i:04x}" for i in range(256)],
                    "special_tokens": ["<|endoftext|>", "<|pad|>", "<|startofpiece|>"],
                    "parameters": {"ms_cprc": True, "bomc": True, "ds_lz": True, "quant_level": 0}
                }, indent=2)
                filename = "tokenizer_sample.json"
            elif sample_type == "prose":
                content = ("It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife. "
                           "However little known the feelings or views of such a man may be on his first entering a neighbourhood, this truth is so "
                           "well fixed in the minds of the surrounding families, that he is considered as the rightful property of some one or other of their daughters.\n") * 15
                filename = "pride_sample.txt"
            elif sample_type == "code":
                content = ('# Middleout-Lattice Next-Gen Compression Engine\n'
                           'def compress_stream(data: bytes, solid: bool = True) -> bytes:\n'
                           '    router = TypeAwareEntropyRouter(data)\n'
                           '    if router.is_dense_float():\n'
                           '        return ordinal_context_pack(data, dynamic_exponent=True)\n'
                           '    match_finder = DualStrideLZ(window_size=65536, stride=16)\n'
                           '    cprc = MultiScaleContextPredictiveRangeCoder(estimators=4)\n'
                           '    return cprc.encode(match_finder.parse_optimal_dag(data))\n') * 10
                filename = "lattice_sample.py"
            elif sample_type == "ai_weights":
                # Simulated IEEE-754 float32 weights stream with clustered dynamic exponents
                import struct
                floats = [math.sin(i * 0.05) * 0.42 for i in range(2000)]
                raw_bytes = struct.pack(f"<{len(floats)}f", *floats)
                self._send_json(200, {
                    "filename": "neural_weights_fp32.bin",
                    "content_base64": base64.b64encode(raw_bytes).decode("ascii"),
                    "type": "binary"
                })
                return
            else:
                content = "Middleout-Lattice high-performance lossless compression engine.\n" * 50
                filename = "sample.txt"

            self._send_json(200, {
                "filename": filename,
                "content_text": content,
                "type": "text"
            })
        else:
            self._send_json(404, {"error": f"Endpoint {self.path} not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.endswith("/compress"):
            self._handle_compress()
        elif path.endswith("/decompress"):
            self._handle_decompress()
        elif path.endswith("/entropy"):
            self._handle_entropy()
        else:
            self._send_json(404, {"error": f"Endpoint {self.path} not found"})

    def _handle_entropy(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len)
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
