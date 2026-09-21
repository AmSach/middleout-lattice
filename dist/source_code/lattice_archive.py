import os
import sys
import struct
import json
import collections
import re
import numpy as np
import zlib
import io
import time

try:
    import zstandard as zstd
except ImportError:
    zstd = None
try:
    import brotli
except ImportError:
    brotli = None

STATIC_KEYWORDS = [
    b'self.', b'def ', b'import ', b'return ', b'class ', b' = ', b'for ', b'in ', b'print(', b'const ',
    b'let ', b'function ', b'while ', b'break ', b'continue ', b'except ', b'try:', b'except Exception:',
    b'async ', b'await ', b'yield ', b'from ', b'global ', b'assert ', b'raise ', b'lambda ', b'with ',
    b'as ', b'pass', b'None', b'True', b'False', b'range(', b'len(', b'append(', b'strip(', b'split(',
    b'join(', b'replace(', b'struct.', b'np.', b'os.', b'sys.', b'time.', b'math.', b'json.', b'open(', b'write('
]

_ELEM_DECODE = [1, 2, 4, 3]
_ELEM_ENCODE = {1: 0, 2: 1, 4: 2, 3: 3}

def _read_varint(stream):
    result = 0
    shift = 0
    while True:
        b = stream.read(1)
        if not b:
            raise EOFError("Unexpected EOF while reading varint")
        val = b[0]
        result |= (val & 0x7F) << shift
        if not (val & 0x80):
            break
        shift += 7
    return result

def _write_varint(stream, val):
    while True:
        tobytes = val & 0x7F
        val >>= 7
        if val > 0:
            stream.write(bytes([tobytes | 0x80]))
        else:
            stream.write(bytes([tobytes]))
            break

def tokenize_code(data):
    try:
        data.decode("ascii")
    except UnicodeDecodeError:
        return None

    lines = data.split(b"\n")
    processed_lines = []
    for line in lines:
        stripped = line.lstrip(b" ")
        indent_len = len(line) - len(stripped)
        if indent_len > 0 and len(stripped) > 0 and not line.startswith(b"\t"):
            depth = indent_len // 4
            remainder = indent_len % 4
            if 1 <= depth <= 31 and remainder == 0:
                depth_token = bytes([0x80 + depth])
                processed_lines.append(depth_token + stripped)
            else:
                processed_lines.append(line)
        else:
            processed_lines.append(line)

    temp = b"\n".join(processed_lines)

    for idx, word in enumerate(STATIC_KEYWORDS):
        token_byte = bytes([0xA0 + idx])
        temp = temp.replace(word, token_byte)

    found = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', temp.decode("utf-8", errors="ignore"))
    counter = collections.Counter(found)
    dynamic_candidates = [word for word, count in counter.most_common(100) if len(word) >= 4 and count >= 3]
    dynamic_candidates = [w for w in dynamic_candidates if w.encode("utf-8") not in STATIC_KEYWORDS][:16]

    mapping = []
    for idx, word in enumerate(dynamic_candidates):
        token_byte = bytes([0xD0 + idx])
        word_bytes = word.encode("utf-8")
        temp = temp.replace(word_bytes, token_byte)
        mapping.append((token_byte, word_bytes))

    dict_header = bytes([len(mapping)])
    for token, word_bytes in mapping:
        dict_header += token + bytes([len(word_bytes)]) + word_bytes

    return dict_header + temp

def detokenize_code(data):
    if len(data) == 0:
        return data
    dict_size = data[0]
    ptr = 1
    mapping = []
    for _ in range(dict_size):
        token_byte = bytes([data[ptr]])
        word_len = data[ptr+1]
        word_bytes = data[ptr+2 : ptr+2+word_len]
        mapping.append((token_byte, word_bytes))
        ptr += 2 + word_len

    body = data[ptr:]

    for token, word_bytes in mapping:
        body = body.replace(token, word_bytes)

    for idx, word in enumerate(STATIC_KEYWORDS):
        token_byte = bytes([0xA0 + idx])
        body = body.replace(token_byte, word)

    lines = body.split(b"\n")
    restored_lines = []
    for line in lines:
        if len(line) > 0 and 0x80 <= line[0] <= 0x9F:
            depth = line[0] - 0x80
            indent = b"    " * depth
            restored_lines.append(indent + line[1:])
        else:
            restored_lines.append(line)
            
    return b"\n".join(restored_lines)

def _load_static_vocab():
    import os, re
    vocab = []
    dict_bytes = b""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "engine", "static_vocab.h"),
        os.path.join(os.path.dirname(__file__), "static_vocab.h"),
        "engine/static_vocab.h"
    ]
    header_path = None
    for p in possible_paths:
        if os.path.exists(p):
            header_path = p
            break
    if header_path:
        with open(header_path, "r", encoding="utf-8") as f:
            content = f.read()
        words = re.findall(r'"([^"]*)"', content)
        vocab = [w.encode("utf-8") for w in words]
        hex_vals = re.findall(r'0x[0-9a-fA-F]{2}', content)
        dict_bytes = bytes(int(h, 16) for h in hex_vals)
    return vocab, dict_bytes

STATIC_VOCAB, STATIC_DICT = _load_static_vocab()
STATIC_VOCAB_MAP = {w: i for i, w in enumerate(STATIC_VOCAB)}

def tokenize_words(data):
    if not STATIC_VOCAB_MAP:
        return data
    parts = re.findall(rb'[a-zA-Z]+|[^a-zA-Z]+', data)
    encoded = bytearray()
    for p in parts:
        if p.isalpha() and all(65 <= b <= 90 or 97 <= b <= 122 for b in p):
            plow = p.lower()
            if plow in STATIC_VOCAB_MAP:
                token_id = STATIC_VOCAB_MAP[plow]
                case_type = -1
                if p.islower():
                    case_type = 0
                elif p.isupper():
                    case_type = 1
                elif p[0:1].isupper() and (len(p) == 1 or p[1:].islower()):
                    case_type = 2
                    
                if case_type != -1:
                    token_id |= (case_type << 13)
                    encoded.append(0x80 | (token_id >> 8))
                    encoded.append(token_id & 0xFF)
                else:
                    encoded.extend(p)
            else:
                encoded.extend(p)
        else:
            for b in p:
                if b >= 128:
                    encoded.append(0xFF)
                encoded.append(b)
    return bytes(encoded)

def detokenize_words(data):
    if not STATIC_VOCAB:
        return data
    output = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0xFF:
            if i + 1 < n:
                output.append(data[i + 1])
                i += 2
            else:
                output.append(b)
                i += 1
        elif 128 <= b < 255:
            if i + 1 >= n:
                output.append(b)
                i += 1
                continue
            next_byte = data[i + 1]
            i += 2
            token_id = ((b & 0x7F) << 8) | next_byte
            vocab_index = token_id & 0x1FFF
            case_type = (token_id >> 13) & 0x03
            if vocab_index >= len(STATIC_VOCAB):
                output.append(b)
                output.append(next_byte)
                continue
            word = bytearray(STATIC_VOCAB[vocab_index])
            if case_type == 1:
                word = bytearray(bytes(word).upper())
            elif case_type == 2:
                if len(word) > 0:
                    word[0:1] = word[0:1].upper()
            output.extend(word)
        else:
            output.append(b)
            i += 1
    return bytes(output)

def shuffle_bytes(data, element_size):
    n = len(data)
    if n == 0:
        return b"", 0
    pad_len = (element_size - (n % element_size)) % element_size
    padded_data = data + b'\x00' * pad_len
    arr = np.frombuffer(padded_data, dtype=np.uint8)
    reshaped = arr.reshape(-1, element_size)
    shuffled = reshaped.T.tobytes()
    # Emulate the prefix behavior
    if element_size == 1:
        prefix = bytes([2, 2])
    elif element_size == 2:
        prefix = bytes([2, 2])
    elif element_size == 3:
        prefix = bytes([3, 3, 3])
    elif element_size == 4:
        prefix = bytes([4, 0, 0, 0])
    else:
        prefix = b""
    return prefix + shuffled, pad_len

def unshuffle_bytes(data, element_size, pad_len):
    if len(data) == 0:
        return b""
    if element_size == 1 or element_size == 2:
        data = data[2:]
    elif element_size == 3:
        data = data[3:]
    elif element_size == 4:
        data = data[4:]
    arr = np.frombuffer(data, dtype=np.uint8)
    unshuffled = arr.reshape(element_size, -1).T.tobytes()
    if pad_len > 0:
        unshuffled = unshuffled[:-pad_len]
    return unshuffled

def choose_file_mode(full_path, rel_path, virtually_lossless=False):
    ext = os.path.splitext(rel_path)[1].lower()
    if virtually_lossless:
        if ext == '.wav':
            return 4, 2
        elif ext in ('.bmp', '.raw_video', '.yuv'):
            return 4, 3
        elif ext in ('.pt', '.pth', '.onnx', '.safetensors', '.bin', '.ckpt', '.h5', '.tflite'):
            return 4, 4
            
    if ext in ('.py', '.cpp', '.h', '.java', '.js', '.ts', '.html', '.css', '.c', '.json', '.md', '.txt', '.csv', '.xml', '.yaml', '.yml', '.ini', '.toml', '.log', '.sh', '.bat', '.ps1'):
        return 2, 1
    elif ext in ('.wav', '.jpg', '.jpeg'):
        return 4, 1
    elif ext in ('.pt', '.pth', '.onnx', '.safetensors', '.bin', '.ckpt', '.h5', '.tflite'):
        return 4, 4  # Return transposed weights mode by default
    else:
        return 0, 1

def mask_and_shuffle(data, ext, elem_size, virtually_lossless=False):
    if not virtually_lossless:
        return shuffle_bytes(data, elem_size)
        
    arr = np.frombuffer(data, dtype=np.uint8).copy()
    n = len(arr)
    
    if ext == '.wav':
        if n > 44:
            arr[44::2] &= 0xF0
        return shuffle_bytes(arr.tobytes(), elem_size)
    elif ext in ('.bmp', '.raw_video', '.yuv'):
        header_len = 54 if ext == '.bmp' else 0
        if n > header_len:
            arr[header_len:] &= 0xF8
        return shuffle_bytes(arr.tobytes(), elem_size)
    elif ext in ('.pt', '.pth', '.onnx', '.safetensors', '.bin', '.ckpt', '.h5', '.tflite'):
        arr[0::4] = 0
        return shuffle_bytes(arr.tobytes(), elem_size)
    else:
        return shuffle_bytes(data, elem_size)

class LatticeArchiveEngine:
    MAGIC = b"LAT!"
    
    @staticmethod
    def compress(src_path, output_archive_path, virtually_lossless=False, solid=True, progress_callback=None):
        t0 = time.perf_counter()
        is_dir = os.path.isdir(src_path)
        files_to_pack = []
        
        if is_dir:
            visited_dirs = set()
            for root, dirs, files in os.walk(src_path, followlinks=False):
                real_root = os.path.abspath(root)
                if real_root in visited_dirs:
                    dirs.clear()
                    continue
                visited_dirs.add(real_root)
                for d in list(dirs):
                    if os.path.islink(os.path.join(root, d)):
                        dirs.remove(d)
                for f in files:
                    full_path = os.path.join(root, f)
                    if os.path.islink(full_path):
                        continue
                    files_to_pack.append((full_path, os.path.relpath(full_path, src_path)))
        else:
            files_to_pack.append((src_path, os.path.basename(src_path)))
            
        total_original_size = sum(os.path.getsize(f[0]) for f in files_to_pack)
        
        dict_samples = []
        text_exts = ('.txt', '.csv', '.json', '.xml', '.html', '.css', '.py', '.js', '.ts', '.c', '.cpp', '.h', '.java', '.md', '.ini', '.yaml', '.yml', '.log')
        total_text_size = 0
        
        for full_path, rel_path in files_to_pack:
            if rel_path.lower().endswith(text_exts):
                sz = os.path.getsize(full_path)
                total_text_size += sz
                if sz > 0 and sz < 2 * 1024 * 1024:
                    with open(full_path, "rb") as f:
                        dict_samples.append(f.read())
                        
        global_dict_data = b""
        if len(dict_samples) >= 4 and zstd:
            try:
                dict_size = 32 * 1024 if total_text_size < 5 * 1024 * 1024 else 112 * 1024
                zdict = zstd.train_dictionary(dict_size, dict_samples)
                global_dict_data = zdict.as_bytes()
            except Exception:
                pass
                
        bytes_processed = 0
        
        with open(output_archive_path, "wb") as arch:
            arch.write(LatticeArchiveEngine.MAGIC)
            _write_varint(arch, len(files_to_pack))
            
            mode_flag = 6 if solid else 5
            mode_flag_pos = arch.tell()
            arch.write(struct.pack("B", mode_flag))
            
            _write_varint(arch, len(global_dict_data))
            if global_dict_data:
                arch.write(global_dict_data)
                
            if mode_flag == 6:
                solid_list = []
                index_buf = io.BytesIO()
                
                for idx, (full_path, rel_path) in enumerate(files_to_pack):
                    file_mode, elem_size = choose_file_mode(full_path, rel_path, virtually_lossless)
                    with open(full_path, "rb") as f:
                        file_data = f.read()
                        
                    if file_mode == 2:
                        tokenized = tokenize_words(file_data)
                        if tokenized is not None:
                            tok_data = b"L_WT" + tokenized
                            if zstd:
                                _dict_data = STATIC_DICT
                                _dict_obj = zstd.ZstdCompressionDict(_dict_data) if _dict_data else None
                                _probe_tok = zstd.ZstdCompressor(level=3, dict_data=_dict_obj)
                                _probe_orig = zstd.ZstdCompressor(level=3)
                                if len(_probe_tok.compress(tok_data)) < len(_probe_orig.compress(file_data)):
                                    file_data = tok_data
                                    
                    orig_size = len(file_data)
                    pad_len = 0
                    
                    if file_mode == 4:
                        processed_data, pad_len = mask_and_shuffle(file_data, os.path.splitext(rel_path)[1].lower(), elem_size, virtually_lossless)
                        orig_size = len(processed_data)
                    else:
                        processed_data = file_data
                        
                    solid_list.append(processed_data)
                    
                    _write_varint(index_buf, len(rel_path.encode('utf-8')))
                    index_buf.write(rel_path.encode('utf-8'))
                    _write_varint(index_buf, orig_size)
                    
                    pk = (pad_len & 0x03) | (_ELEM_ENCODE[elem_size] << 2) | (0 << 4) | (file_mode << 5)
                    index_buf.write(bytes([pk]))
                    
                    bytes_processed += len(file_data)
                    if progress_callback:
                        progress_callback(idx, len(files_to_pack), rel_path, bytes_processed)
                
                all_data = b"".join(solid_list)
                
                dict_to_use = global_dict_data if global_dict_data else STATIC_DICT
                comp_zstd = b""
                if zstd:
                    z_comp = zstd.ZstdCompressor(level=15, dict_data=zstd.ZstdCompressionDict(dict_to_use) if dict_to_use else None)
                    comp_zstd = z_comp.compress(all_data)
                elif brotli:
                    comp_zstd = brotli.compress(all_data, quality=4)
                else:
                    comp_zstd = all_data
                    
                comp_bwt = b""
                if zstd and 4096 <= len(all_data) <= 1500000:
                    try:
                        from middleout_lattice.transforms import fast_bwt, mtf_encode, rle_encode
                        bwt_bytes, bwt_p_idx = fast_bwt(all_data)
                        mtf_bytes = mtf_encode(bwt_bytes)
                        rle_bytes = rle_encode(mtf_bytes)
                        bwt_payload = struct.pack("<I", bwt_p_idx) + rle_bytes
                        comp_bwt = zstd.ZstdCompressor(level=22).compress(bwt_payload)
                    except Exception:
                        pass
                
                if comp_bwt and len(comp_bwt) < len(comp_zstd):
                    comp_data = comp_bwt
                    mode_flag = 7
                else:
                    comp_data = comp_zstd
                    mode_flag = 6
                
                curr_pos = arch.tell()
                arch.seek(mode_flag_pos)
                arch.write(struct.pack("B", mode_flag))
                arch.seek(curr_pos)
                    
                _write_varint(arch, len(index_buf.getvalue()))
                arch.write(index_buf.getvalue())
                arch.write(comp_data)
                
            else:
                z_ctx = None
                if global_dict_data and zstd:
                    z_ctx = zstd.ZstdCompressor(level=15, dict_data=zstd.ZstdCompressionDict(global_dict_data))
                    
                for idx, (full_path, rel_path) in enumerate(files_to_pack):
                    file_mode, elem_size = choose_file_mode(full_path, rel_path, virtually_lossless)
                    with open(full_path, "rb") as f:
                        file_data = f.read()
                        
                    orig_size = len(file_data)
                    pad_len = 0
                    
                    if file_mode == 4:
                        processed_data, pad_len = mask_and_shuffle(file_data, os.path.splitext(rel_path)[1].lower(), elem_size, virtually_lossless)
                        orig_size = len(processed_data)
                    else:
                        processed_data = file_data
                        
                    if file_mode == 2:
                        tokenized = tokenize_words(processed_data)
                        
                        comp_zstd_normal = b""
                        if zstd:
                            z_comp = zstd.ZstdCompressor(level=22, dict_data=zstd.ZstdCompressionDict(STATIC_DICT) if STATIC_DICT else None)
                            comp_zstd_normal = z_comp.compress(tokenized)
                        elif brotli:
                            comp_zstd_normal = brotli.compress(tokenized, quality=4)
                        else:
                            comp_zstd_normal = tokenized
                            
                        comp_bwt = b""
                        if zstd and 4096 <= len(tokenized) <= 1500000:
                            try:
                                from middleout_lattice.transforms import fast_bwt, mtf_encode, rle_encode
                                bwt_bytes, p_idx = fast_bwt(tokenized)
                                mtf_bytes = mtf_encode(bwt_bytes)
                                rle_bytes = rle_encode(mtf_bytes)
                                bwt_payload = struct.pack("<I", p_idx) + rle_bytes
                                comp_bwt = zstd.ZstdCompressor(level=22).compress(bwt_payload)
                            except Exception:
                                pass
                                
                        if comp_bwt and len(comp_bwt) < len(comp_zstd_normal):
                            compressed_payload = comp_bwt
                            file_mode = 3
                        else:
                            compressed_payload = comp_zstd_normal
                            file_mode = 2
                    elif file_mode == 4:
                        if zstd:
                            z_comp = zstd.ZstdCompressor(level=19)
                            compressed_payload = z_comp.compress(processed_data)
                        elif brotli:
                            compressed_payload = brotli.compress(processed_data, quality=4)
                        else:
                            compressed_payload = processed_data
                    else:
                        comp_level = 15 if orig_size < 10 * 1024 * 1024 else 12
                        if zstd:
                            z_comp = z_ctx if z_ctx else zstd.ZstdCompressor(level=comp_level)
                            compressed_payload = z_comp.compress(processed_data)
                        elif brotli:
                            compressed_payload = brotli.compress(processed_data, quality=4)
                        else:
                            compressed_payload = processed_data
                        
                    rel_bytes = rel_path.encode("utf-8")
                    _write_varint(arch, len(rel_bytes))
                    arch.write(rel_bytes)
                    _write_varint(arch, orig_size)
                    _write_varint(arch, len(compressed_payload))
                    
                    pk = (pad_len & 0x03) | (_ELEM_ENCODE[elem_size] << 2) | (0 << 4) | (file_mode << 5)
                    arch.write(bytes([pk]))
                    arch.write(compressed_payload)
                    
                    bytes_processed += len(file_data)
                    if progress_callback:
                        progress_callback(idx, len(files_to_pack), rel_path, bytes_processed)

        # Integrity footer
        with open(output_archive_path, "rb") as f:
            payload = f.read()
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        with open(output_archive_path, "ab") as f:
            f.write(b"LCRC" + struct.pack("<I", crc))
            
        return mode_flag, total_original_size, len(files_to_pack)

    @staticmethod
    def decompress(archive_path, dest_dir, progress_callback=None):
        total_size = os.path.getsize(archive_path)
        with open(archive_path, "rb") as f:
            raw = f.read()
        
        if len(raw) < 8 or raw[-8:-4] != b"LCRC":
            raise ValueError("INTEGRITY FAILURE: Missing CRC32 footer.")
        
        stored_crc = struct.unpack("<I", raw[-4:])[0]
        payload = raw[:-8]
        computed_crc = zlib.crc32(payload) & 0xFFFFFFFF
        if stored_crc != computed_crc:
            raise ValueError(f"INTEGRITY FAILURE: CRC32 mismatch. Expected {stored_crc}, got {computed_crc}")
            
        stream = io.BytesIO(payload)
        magic = stream.read(4)
        if magic != LatticeArchiveEngine.MAGIC:
            raise ValueError("Invalid magic header")
            
        num_files = _read_varint(stream)
        global_mode = struct.unpack("B", stream.read(1))[0]
        
        dict_size = _read_varint(stream)
        global_dict_data = stream.read(dict_size)
        
        z_dctx = None
        if zstd:
            dict_to_use = global_dict_data if global_dict_data else STATIC_DICT
            if dict_to_use:
                z_dctx = zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(dict_to_use))
            
        bytes_processed = 0
        os.makedirs(dest_dir, exist_ok=True)
        
        if global_mode == 6 or global_mode == 7:
            idx_len = _read_varint(stream)
            idx_data = stream.read(idx_len)
            comp_data = stream.read()
            
            # Decompress solid block
            try:
                if global_mode == 7:
                    raw_block = zstd.ZstdDecompressor().decompress(comp_data)
                    p_idx = struct.unpack("<I", raw_block[:4])[0]
                    rle_bytes = raw_block[4:]
                    from middleout_lattice.transforms import fast_ibwt, mtf_decode, rle_decode
                    mtf_bytes = rle_decode(rle_bytes)
                    bwt_bytes = mtf_decode(mtf_bytes)
                    all_data = fast_ibwt(bwt_bytes, p_idx)
                else:
                    if z_dctx:
                        all_data = z_dctx.decompress(comp_data)
                    elif zstd:
                        all_data = zstd.ZstdDecompressor().decompress(comp_data)
                    else:
                        all_data = comp_data
            except Exception:
                try:
                    all_data = brotli.decompress(comp_data)
                except Exception:
                    all_data = comp_data
                    
            idx_stream = io.BytesIO(idx_data)
            all_stream = io.BytesIO(all_data)
            
            for idx in range(num_files):
                path_len = _read_varint(idx_stream)
                rel_path = idx_stream.read(path_len).decode("utf-8")
                orig_size = _read_varint(idx_stream)
                
                pk = idx_stream.read(1)[0]
                pad_len = pk & 0x03
                elem_size = _ELEM_DECODE[(pk >> 2) & 0x03]
                file_mode = (pk >> 5) & 0x07
                
                file_data = all_stream.read(orig_size)
                
                if file_mode == 4:
                    file_data = unshuffle_bytes(file_data, elem_size, pad_len)
                
                if file_data.startswith(b"L_WT"):
                    file_data = detokenize_words(file_data[4:])
                elif file_data.startswith(b"L_TOK"):
                    file_data = detokenize_code(file_data[5:])
                    
                out_path = os.path.join(dest_dir, rel_path)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "wb") as out_f:
                    out_f.write(file_data)
                    
                bytes_processed += orig_size
                if progress_callback:
                    progress_callback(idx, num_files, rel_path, bytes_processed)
                    
        else:
            for idx in range(num_files):
                path_len = _read_varint(stream)
                rel_path = stream.read(path_len).decode("utf-8")
                orig_size = _read_varint(stream)
                comp_size = _read_varint(stream)
                
                pk = stream.read(1)[0]
                pad_len = pk & 0x03
                elem_size = _ELEM_DECODE[(pk >> 2) & 0x03]
                file_mode = (pk >> 5) & 0x07
                
                comp_data = stream.read(comp_size)
                
                if file_mode == 3:
                    try:
                        raw_block = zstd.ZstdDecompressor().decompress(comp_data)
                        p_idx = struct.unpack("<I", raw_block[:4])[0]
                        rle_bytes = raw_block[4:]
                        from middleout_lattice.transforms import fast_ibwt, mtf_decode, rle_decode
                        mtf_bytes = rle_decode(rle_bytes)
                        bwt_bytes = mtf_decode(mtf_bytes)
                        tokenized = fast_ibwt(bwt_bytes, p_idx)
                        file_data = detokenize_words(tokenized)
                    except Exception:
                        file_data = comp_data
                elif file_mode == 2:
                    try:
                        if zstd:
                            dctx = zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(STATIC_DICT) if STATIC_DICT else None)
                            tokenized = dctx.decompress(comp_data)
                            file_data = detokenize_words(tokenized)
                        elif brotli:
                            tokenized = brotli.decompress(comp_data)
                            file_data = detokenize_words(tokenized)
                        else:
                            file_data = detokenize_words(comp_data)
                    except Exception:
                        file_data = comp_data
                else:
                    try:
                        if z_dctx:
                            file_data = z_dctx.decompress(comp_data, max_output_size=orig_size)
                        elif zstd:
                            file_data = zstd.ZstdDecompressor().decompress(comp_data, max_output_size=orig_size)
                        else:
                            file_data = comp_data
                    except Exception:
                        try:
                            file_data = brotli.decompress(comp_data)
                        except Exception:
                            file_data = comp_data
                        
                if file_mode == 4:
                    file_data = unshuffle_bytes(file_data, elem_size, pad_len)
                
                if file_data.startswith(b"L_WT"):
                    file_data = detokenize_words(file_data[4:])
                elif file_data.startswith(b"L_TOK"):
                    file_data = detokenize_code(file_data[5:])
                    
                out_path = os.path.join(dest_dir, rel_path)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "wb") as out_f:
                    out_f.write(file_data)
                    
                bytes_processed += orig_size
                if progress_callback:
                    progress_callback(idx, num_files, rel_path, bytes_processed)
