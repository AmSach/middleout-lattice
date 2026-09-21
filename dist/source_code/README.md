# MiddleOut Lattice

Neural compression for model files, tensor archives, and arbitrary data.

## Features

- **Neural Compression**: Transformer-based byte-level compression with arithmetic coding
- **Traditional Codecs**: LZMA, zlib, bz2 with automatic best-selection
- **Mosaic Transform**: Entropy-aware byte-plane transformation
- **Corpus Compression**: Shared-dictionary compression across multiple files
- **Tensor Compression**: Specialized compression for safetensors/model weights

## Installation

```bash
pip install -e .
```

## Quick Start

### Train a Neural Compression Model

```bash
# Prepare training data (Gutenberg books + sample code)
python scripts/train.py --prepare-data --data-dir ./data --gutenberg --gutenberg-count 2000

# Train medium model (~25M params)
python scripts/train.py --train \
    --data-dir ./data \
    --output ./checkpoints/model.pt \
    --model-config medium \
    --epochs 10 \
    --batch-size 16 \
    --device cuda

# Benchmark against traditional compressors
python scripts/train.py --benchmark \
    --output ./checkpoints/model.pt \
    --test-dir ./test_files
```

### Lightning AI Training

1. Create a Lightning Studio with A100/H100 GPU
2. Clone/upload this repo
3. Run training:

```bash
pip install -e .
python scripts/train.py --prepare-data --data-dir ./data --gutenberg --gutenberg-count 3000
python scripts/train.py --train \
    --data-dir ./data \
    --output ./checkpoints/model.pt \
    --model-config medium \
    --epochs 5 \
    --batch-size 8 \
    --device cuda
```

4. Download the trained model from `./checkpoints/model.pt`

## Model Sizes

| Config | Parameters | Context | VRAM | Train Time (1GB) |
|--------|-----------|---------|------|------------------|
| small  | ~10M      | 1024    | 4GB  | ~1 hour         |
| medium | ~25M      | 2048    | 8GB  | ~3 hours        |
| large  | ~50M      | 4096    | 16GB | ~8 hours        |

## Expected Results

After training on 2-5GB of text/code:

| Compressor | Text | Code | JSON | Mixed |
|------------|------|------|------|-------|
| tar.bz2    | 3.2x | 3.5x | 4.1x | 3.0x  |
| Neural     | 4-5x | 5-7x | 6-8x | 4-6x  |

## Usage

### Compress with Neural Model

```python
from middleout_lattice.neural import load_model
from middleout_lattice.neural_codec import compress_with_model, decompress_with_model

model = load_model("model.pt", device="cuda")

# Compress
compressed = compress_with_model(model, data)

# Decompress
decompressed = decompress_with_model(model, compressed)

assert data == decompressed  # Lossless
```

### Compress Directory

```python
from middleout_lattice import compress_directory, decompress_directory
from pathlib import Path

# Compress
manifest = compress_directory(Path("./my_model"), Path("./compressed"))

# Decompress
decompress_directory(manifest, Path("./restored"))
```

## Architecture

The neural compression model uses:

1. **Byte-level tokenization**: Each byte is a token (vocab size = 256)
2. **Causal transformer**: Predicts next byte from context
3. **Arithmetic coding**: Uses probability distribution for compression
4. **Modern architecture**: RMSNorm, SwiGLU, pre-norm residual

## Training Tips

- **Data**: Train on data similar to what you'll compress
- **Context**: Longer context = better compression of repetitive data
- **Fine-tuning**: Pre-train on general text, fine-tune on your domain
- **Batch size**: As large as VRAM allows
- **Learning rate**: 3e-4 default, lower (1e-4) for large models

## License

MIT
