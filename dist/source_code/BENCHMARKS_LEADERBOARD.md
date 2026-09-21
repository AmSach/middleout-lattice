# Industrial-Grade Benchmarks & Compressor Leaderboard

This leaderboard documents the compression ratios, speeds, and lossless integrity check results of **Middleout-Lattice** against standard compressors.

## Literature (Alice) — `alice.txt` (Original: 151,191 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice C++ (Non-Solid)** | **40,996 B** | **3.688x** | **0.1472s** | **0.0268s** | ✓ YES |
| 2 | **Lattice Python (Non-Solid)** | **40,996 B** | **3.688x** | **0.3727s** | **0.2365s** | ✓ YES |
| 3 | **Lattice C++ (Solid)** | **41,032 B** | **3.685x** | **0.1616s** | **0.0253s** | ✓ YES |
| 4 | **Lattice Python (Solid)** | **41,032 B** | **3.685x** | **1328.1390s** | **0.2354s** | ✓ YES |
| 5 | Bzip2 (-9) | 42,743 B | 3.537x | 0.0156s | 0.0052s | ✓ YES |
| 6 | Brotli (L11) | 45,885 B | 3.295x | 0.3233s | 0.0012s | ✓ YES |
| 7 | LZMA (Preset 9) | 47,636 B | 3.174x | 0.0737s | 0.0054s | ✓ YES |
| 8 | Zstd (L19) | 48,280 B | 3.132x | 0.0797s | 0.0005s | ✓ YES |
| 9 | Zstd (L22) | 48,280 B | 3.132x | 0.0735s | 0.0005s | ✓ YES |
| 10 | Brotli (L7) | 50,340 B | 3.003x | 0.0142s | 0.0012s | ✓ YES |
| 11 | Zstd (L12) | 50,521 B | 2.993x | 0.0182s | 0.0006s | ✓ YES |
| 12 | Gzip (-9) | 53,357 B | 2.834x | 0.0221s | 0.0011s | ✓ YES |
| 13 | Brotli (L3) | 55,980 B | 2.701x | 0.0036s | 0.0015s | ✓ YES |
| 14 | Zstd (L3) | 56,082 B | 2.696x | 0.0022s | 0.0004s | ✓ YES |

## Literature (Pride) — `pride.txt` (Original: 738,046 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice C++ (Solid)** | **184,932 B** | **3.991x** | **0.5429s** | **0.0555s** | ✓ YES |
| 2 | **Lattice Python (Solid)** | **184,932 B** | **3.991x** | **1.8924s** | **1.1010s** | ✓ YES |
| 3 | **Lattice C++ (Non-Solid)** | **185,000 B** | **3.989x** | **0.7111s** | **0.0639s** | ✓ YES |
| 4 | **Lattice Python (Non-Solid)** | **185,000 B** | **3.989x** | **1.8936s** | **1.2585s** | ✓ YES |
| 5 | Bzip2 (-9) | 186,325 B | 3.961x | 0.0903s | 0.0505s | ✓ YES |
| 6 | Brotli (L11) | 212,481 B | 3.473x | 1.9780s | 0.0029s | ✓ YES |
| 7 | LZMA (Preset 9) | 216,036 B | 3.416x | 0.5948s | 0.0166s | ✓ YES |
| 8 | Zstd (L19) | 218,703 B | 3.375x | 0.4604s | 0.0022s | ✓ YES |
| 9 | Zstd (L22) | 218,703 B | 3.375x | 0.4005s | 0.0015s | ✓ YES |
| 10 | Zstd (L12) | 232,728 B | 3.171x | 0.0902s | 0.0015s | ✓ YES |
| 11 | Brotli (L7) | 237,530 B | 3.107x | 0.0813s | 0.0028s | ✓ YES |
| 12 | Zstd (L3) | 257,425 B | 2.867x | 0.0094s | 0.0023s | ✓ YES |
| 13 | Gzip (-9) | 264,731 B | 2.788x | 0.1119s | 0.0037s | ✓ YES |
| 14 | Brotli (L3) | 271,878 B | 2.715x | 0.0141s | 0.0045s | ✓ YES |

## C++ Code (stb_image) — `stb_image.h` (Original: 294,663 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | Brotli (L7) | 92 B | 3202.859x | 0.0014s | 0.0005s | ✓ YES |
| 2 | Brotli (L11) | 98 B | 3006.765x | 0.0298s | 0.0004s | ✓ YES |
| 3 | Brotli (L3) | 102 B | 2888.853x | 0.0010s | 0.0007s | ✓ YES |
| 4 | Zstd (L19) | 131 B | 2249.336x | 0.0033s | 0.0001s | ✓ YES |
| 5 | Zstd (L22) | 131 B | 2249.336x | 0.0039s | 0.0003s | ✓ YES |
| 6 | Zstd (L3) | 134 B | 2198.978x | 0.0004s | 0.0001s | ✓ YES |
| 7 | Zstd (L12) | 134 B | 2198.978x | 0.0020s | 0.0002s | ✓ YES |
| 8 | Bzip2 (-9) | 135 B | 2182.689x | 0.0082s | 0.0013s | ✓ YES |
| 9 | **Lattice C++ (Non-Solid)** | **137 B** | **2150.825x** | **0.3601s** | **0.0224s** | ✓ YES |
| 10 | **Lattice Python (Non-Solid)** | **137 B** | **2150.825x** | **1.2500s** | **0.0776s** | ✓ YES |
| 11 | **Lattice Python (Solid)** | **141 B** | **2089.809x** | **1.2060s** | **0.1009s** | ✓ YES |
| 12 | **Lattice C++ (Solid)** | **142 B** | **2075.092x** | **0.3788s** | **0.0236s** | ✓ YES |
| 13 | LZMA (Preset 9) | 264 B | 1116.148x | 0.0617s | 0.0011s | ✓ YES |
| 14 | Gzip (-9) | 1,123 B | 262.389x | 0.0039s | 0.0006s | ✓ YES |

## Python Code (lattice_archive) — `lattice_archive.py` (Original: 29,890 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice C++ (Non-Solid)** | **4,986 B** | **5.995x** | **0.0656s** | **0.0216s** | ✓ YES |
| 2 | **Lattice Python (Non-Solid)** | **4,986 B** | **5.995x** | **0.1014s** | **0.0201s** | ✓ YES |
| 3 | **Lattice C++ (Solid)** | **5,020 B** | **5.954x** | **0.0710s** | **0.0239s** | ✓ YES |
| 4 | **Lattice Python (Solid)** | **5,020 B** | **5.954x** | **0.0870s** | **0.0095s** | ✓ YES |
| 5 | Brotli (L11) | 5,301 B | 5.639x | 0.0605s | 0.0002s | ✓ YES |
| 6 | Zstd (L19) | 5,612 B | 5.326x | 0.0211s | 0.0001s | ✓ YES |
| 7 | Zstd (L22) | 5,612 B | 5.326x | 0.0236s | 0.0001s | ✓ YES |
| 8 | LZMA (Preset 9) | 5,616 B | 5.322x | 0.0277s | 0.0009s | ✓ YES |
| 9 | Bzip2 (-9) | 5,713 B | 5.232x | 0.0033s | 0.0009s | ✓ YES |
| 10 | Brotli (L7) | 5,716 B | 5.229x | 0.0061s | 0.0001s | ✓ YES |
| 11 | Zstd (L12) | 5,843 B | 5.116x | 0.0029s | 0.0001s | ✓ YES |
| 12 | Gzip (-9) | 5,879 B | 5.084x | 0.0038s | 0.0002s | ✓ YES |
| 13 | Brotli (L3) | 6,432 B | 4.647x | 0.0005s | 0.0001s | ✓ YES |
| 14 | Zstd (L3) | 6,591 B | 4.535x | 0.0005s | 0.0001s | ✓ YES |

## Structured JSON Data — `bpe_tokenizer.json` (Original: 12,559 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice C++ (Non-Solid)** | **432 B** | **29.072x** | **0.0529s** | **0.0222s** | ✓ YES |
| 2 | **Lattice Python (Non-Solid)** | **432 B** | **29.072x** | **0.0601s** | **0.0341s** | ✓ YES |
| 3 | **Lattice C++ (Solid)** | **447 B** | **28.096x** | **0.0594s** | **0.0213s** | ✓ YES |
| 4 | **Lattice Python (Solid)** | **447 B** | **28.096x** | **0.0629s** | **0.0326s** | ✓ YES |
| 5 | Brotli (L3) | 511 B | 24.577x | 0.0002s | 0.0001s | ✓ YES |
| 6 | Brotli (L7) | 515 B | 24.386x | 0.0029s | 0.0001s | ✓ YES |
| 7 | Brotli (L11) | 525 B | 23.922x | 0.0106s | 0.0001s | ✓ YES |
| 8 | Zstd (L3) | 608 B | 20.656x | 0.0001s | 0.0000s | ✓ YES |
| 9 | LZMA (Preset 9) | 616 B | 20.388x | 0.0170s | 0.0003s | ✓ YES |
| 10 | Zstd (L19) | 672 B | 18.689x | 0.0044s | 0.0000s | ✓ YES |
| 11 | Zstd (L22) | 672 B | 18.689x | 0.0041s | 0.0001s | ✓ YES |
| 12 | Zstd (L12) | 734 B | 17.110x | 0.0010s | 0.0000s | ✓ YES |
| 13 | Bzip2 (-9) | 780 B | 16.101x | 0.0008s | 0.0002s | ✓ YES |
| 14 | Gzip (-9) | 1,213 B | 10.354x | 0.0004s | 0.0001s | ✓ YES |

## Weights small (380KB) — `block_autoencoder.pt` (Original: 389,120 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice C++ (Non-Solid)** | **330,125 B** | **1.179x** | **0.1004s** | **0.0312s** | ✓ YES |
| 2 | **Lattice Python (Non-Solid)** | **330,125 B** | **1.179x** | **0.1277s** | **0.0159s** | ✓ YES |
| 3 | **Lattice Python (Solid)** | **330,616 B** | **1.177x** | **1.4787s** | **0.0220s** | ✓ YES |
| 4 | **Lattice C++ (Solid)** | **333,661 B** | **1.166x** | **0.3215s** | **0.0338s** | ✓ YES |
| 5 | Brotli (L11) | 357,041 B | 1.090x | 1.5384s | 0.0066s | ✓ YES |
| 6 | LZMA (Preset 9) | 359,336 B | 1.083x | 0.1320s | 0.0306s | ✓ YES |
| 7 | Brotli (L3) | 359,600 B | 1.082x | 0.0032s | 0.0033s | ✓ YES |
| 8 | Zstd (L12) | 359,611 B | 1.082x | 0.0035s | 0.0008s | ✓ YES |
| 9 | Brotli (L7) | 359,632 B | 1.082x | 0.0120s | 0.0050s | ✓ YES |
| 10 | Zstd (L3) | 359,862 B | 1.081x | 0.0017s | 0.0007s | ✓ YES |
| 11 | Zstd (L19) | 359,877 B | 1.081x | 0.0792s | 0.0006s | ✓ YES |
| 12 | Zstd (L22) | 359,877 B | 1.081x | 0.0702s | 0.0009s | ✓ YES |
| 13 | Gzip (-9) | 360,368 B | 1.080x | 0.0268s | 0.0027s | ✓ YES |
| 14 | Bzip2 (-9) | 370,546 B | 1.050x | 0.0702s | 0.0318s | ✓ YES |

## Weights large (81MB) — `best_model.pt` (Original: 81,788,928 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice C++ (Non-Solid)** | **68,194,880 B** | **1.199x** | **51.8804s** | **1.2791s** | ✓ YES |
| 2 | **Lattice Python (Non-Solid)** | **68,194,880 B** | **1.199x** | **52.5482s** | **0.4873s** | ✓ YES |
| 3 | **Lattice Python (Solid)** | **68,786,763 B** | **1.189x** | **15.6324s** | **0.4997s** | ✓ YES |
| 4 | **Lattice C++ (Solid)** | **69,123,654 B** | **1.183x** | **24.1339s** | **1.3693s** | ✓ YES |
| 5 | LZMA (Preset 9) | 74,388,864 B | 1.099x | 57.2342s | 6.4071s | ✓ YES |
| 6 | Brotli (L11) | 75,032,589 B | 1.090x | 348.1177s | 1.2687s | ✓ YES |
| 7 | Zstd (L12) | 75,589,850 B | 1.082x | 0.4199s | 0.1537s | ✓ YES |
| 8 | Brotli (L3) | 75,591,520 B | 1.082x | 0.6418s | 0.8092s | ✓ YES |
| 9 | Brotli (L7) | 75,596,033 B | 1.082x | 1.7918s | 0.7630s | ✓ YES |
| 10 | Zstd (L22) | 75,608,426 B | 1.082x | 37.0492s | 0.2070s | ✓ YES |
| 11 | Zstd (L19) | 75,608,431 B | 1.082x | 32.0222s | 0.1672s | ✓ YES |
| 12 | Zstd (L3) | 75,681,983 B | 1.081x | 0.4618s | 0.1803s | ✓ YES |
| 13 | Gzip (-9) | 75,750,720 B | 1.080x | 6.5625s | 0.6419s | ✓ YES |
| 14 | Bzip2 (-9) | 77,624,812 B | 1.054x | 14.7011s | 7.8093s | ✓ YES |

## JPEG Image — `mingpt.jpg` (Original: 118,276 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | Brotli (L11) | 113,177 B | 1.045x | 0.6384s | 0.0014s | ✓ YES |
| 2 | Brotli (L7) | 113,915 B | 1.038x | 0.0090s | 0.0011s | ✓ YES |
| 3 | Zstd (L19) | 113,944 B | 1.038x | 0.0220s | 0.0001s | ✓ YES |
| 4 | Zstd (L22) | 113,944 B | 1.038x | 0.0233s | 0.0002s | ✓ YES |
| 5 | **Lattice C++ (Non-Solid)** | **113,981 B** | **1.038x** | **0.0526s** | **0.0209s** | ✓ YES |
| 6 | **Lattice Python (Non-Solid)** | **113,981 B** | **1.038x** | **0.0381s** | **0.0136s** | ✓ YES |
| 7 | Gzip (-9) | 114,124 B | 1.036x | 0.0059s | 0.0004s | ✓ YES |
| 8 | LZMA (Preset 9) | 114,448 B | 1.033x | 0.0549s | 0.0092s | ✓ YES |
| 9 | Brotli (L3) | 114,530 B | 1.033x | 0.0009s | 0.0003s | ✓ YES |
| 10 | Zstd (L12) | 114,532 B | 1.033x | 0.0018s | 0.0000s | ✓ YES |
| 11 | **Lattice C++ (Solid)** | **114,593 B** | **1.032x** | **0.1388s** | **0.0232s** | ✓ YES |
| 12 | **Lattice Python (Solid)** | **114,593 B** | **1.032x** | **0.3700s** | **0.0108s** | ✓ YES |
| 13 | Zstd (L3) | 114,712 B | 1.031x | 0.0007s | 0.0000s | ✓ YES |
| 14 | Bzip2 (-9) | 114,930 B | 1.029x | 0.0206s | 0.0079s | ✓ YES |

## Codebase Directory (minGPT) — `minGPT` (Original: 1,699,930 bytes)

| Rank | Compressor | Compressed Size | Compression Ratio | Comp Time | Decomp Time | Lossless |
| --- | :--- | ---: | ---: | ---: | ---: | :---: |
| 1 | **Lattice Python (Solid)** | **1,568,549 B** | **1.084x** | **0.1950s** | **0.0644s** | ✓ YES |
| 2 | **Lattice C++ (Solid)** | **1,570,778 B** | **1.082x** | **0.1490s** | **0.0851s** | ✓ YES |
| 3 | **Lattice Python (Non-Solid)** | **1,654,839 B** | **1.027x** | **0.1550s** | **0.0513s** | ✓ YES |
| 4 | **Lattice C++ (Non-Solid)** | **1,656,760 B** | **1.026x** | **0.1553s** | **0.0879s** | ✓ YES |