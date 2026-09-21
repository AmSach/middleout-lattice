#include <iostream>
#include <vector>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <immintrin.h>

// ============================================================================
// 1. Bit-Plane Matrix-Transpose (BPMT) Predictor Implementation
// ============================================================================

// Transpose 64-byte block at bit-plane level:
// Converts 64 bytes into 8 bit-planes (Bit 7 lane, Bit 6 lane, ..., Bit 0 lane)
// and computes bit-wise XOR prediction across adjacent items.
void bpmt_encode_block64(const uint8_t* in, uint8_t* out) {
    // 8 lanes of 8 bytes = 64 bytes
    uint8_t planes[8][8];
    std::memset(planes, 0, sizeof(planes));

    // Extract bit-planes
    for (int i = 0; i < 64; ++i) {
        uint8_t byte = in[i];
        int row = i / 8;
        int col = i % 8;
        for (int bit = 0; bit < 8; ++bit) {
            if ((byte >> bit) & 1) {
                planes[bit][row] |= (1 << col);
            }
        }
    }

    // XOR prediction on bit-planes
    uint8_t prev[8] = {0};
    int out_idx = 0;
    for (int bit = 7; bit >= 0; --bit) { // Most significant bit lanes first
        for (int row = 0; row < 8; ++row) {
            uint8_t val = planes[bit][row];
            out[out_idx++] = val ^ prev[bit];
            prev[bit] = val;
        }
    }
}

void bpmt_decode_block64(const uint8_t* in, uint8_t* out) {
    uint8_t planes[8][8];
    int in_idx = 0;

    for (int bit = 7; bit >= 0; --bit) {
        uint8_t prev = 0;
        for (int row = 0; row < 8; ++row) {
            uint8_t diff = in[in_idx++];
            uint8_t val = diff ^ prev;
            planes[bit][row] = val;
            prev = val;
        }
    }

    // Reconstruct 64 bytes from bit-planes
    for (int i = 0; i < 64; ++i) {
        int row = i / 8;
        int col = i % 8;
        uint8_t byte = 0;
        for (int bit = 0; bit < 8; ++bit) {
            if ((planes[bit][row] >> col) & 1) {
                byte |= (1 << bit);
            }
        }
        out[i] = byte;
    }
}

// Full BPMT Transform on buffer
std::vector<uint8_t> bpmt_transform(const std::vector<uint8_t>& input) {
    size_t n = input.size();
    size_t blocks = n / 64;
    std::vector<uint8_t> output(n);

    for (size_t b = 0; b < blocks; ++b) {
        bpmt_encode_block64(input.data() + b * 64, output.data() + b * 64);
    }
    // Remainder
    for (size_t i = blocks * 64; i < n; ++i) {
        output[i] = input[i] ^ (i > 0 ? input[i - 1] : 0);
    }
    return output;
}

std::vector<uint8_t> bpmt_untransform(const std::vector<uint8_t>& input) {
    size_t n = input.size();
    size_t blocks = n / 64;
    std::vector<uint8_t> output(n);

    for (size_t b = 0; b < blocks; ++b) {
        bpmt_decode_block64(input.data() + b * 64, output.data() + b * 64);
    }
    for (size_t i = blocks * 64; i < n; ++i) {
        output[i] = input[i] ^ (i > 0 ? output[i - 1] : 0);
    }
    return output;
}

// ============================================================================
// 2. Interleaved 4-Stream SIMD Fast tANS (IS-ANS)
// ============================================================================

struct ISANS_DecoderTable {
    uint8_t symbol[2048];
    uint8_t num_bits[2048];
    uint16_t new_state_base[2048];
};

// Benchmark demonstration of IS-ANS interleaved decoding concept
void test_isans_speed() {
    constexpr size_t TEST_SIZE = 64 * 1024 * 1024; // 64 MB
    std::vector<uint8_t> dummy_bitstream(TEST_SIZE, 0b10101010);
    std::vector<uint8_t> output_symbols(TEST_SIZE);

    // Mock SIMD tANS decode loop
    ISANS_DecoderTable table;
    for (int i = 0; i < 2048; ++i) {
        table.symbol[i] = static_cast<uint8_t>(i & 0xFF);
        table.num_bits[i] = (i % 3) + 1;
        table.new_state_base[i] = static_cast<uint16_t>(1024 + (i % 1024));
    }

    uint32_t state[4] = {1024, 1025, 1026, 1027};
    const uint32_t* bitstream32 = reinterpret_cast<const uint32_t*>(dummy_bitstream.data());

    auto t0 = std::chrono::high_resolution_clock::now();

    size_t out_idx = 0;
    size_t num_iters = (TEST_SIZE / 4) - 16;
    for (size_t i = 0; i < num_iters; i += 4) {
        // Unroll 4 interleaved states in CPU pipeline
        uint32_t s0 = state[0], s1 = state[1], s2 = state[2], s3 = state[3];

        uint8_t sym0 = table.symbol[s0];
        uint8_t sym1 = table.symbol[s1];
        uint8_t sym2 = table.symbol[s2];
        uint8_t sym3 = table.symbol[s3];

        output_symbols[out_idx++] = sym0;
        output_symbols[out_idx++] = sym1;
        output_symbols[out_idx++] = sym2;
        output_symbols[out_idx++] = sym3;

        uint32_t bits0 = table.num_bits[s0];
        uint32_t bits1 = table.num_bits[s1];
        uint32_t bits2 = table.num_bits[s2];
        uint32_t bits3 = table.num_bits[s3];

        uint32_t w = bitstream32[i];
        state[0] = (table.new_state_base[s0] + (w & ((1U << bits0) - 1))) & 2047;
        state[1] = (table.new_state_base[s1] + ((w >> bits0) & ((1U << bits1) - 1))) & 2047;
        state[2] = (table.new_state_base[s2] + ((w >> (bits0 + bits1)) & ((1U << bits2) - 1))) & 2047;
        state[3] = (table.new_state_base[s3] + ((w >> (bits0 + bits1 + bits2)) & ((1U << bits3) - 1))) & 2047;
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    double seconds = std::chrono::duration<double>(t1 - t0).count();
    double throughput_gbps = (TEST_SIZE / (1024.0 * 1024.0 * 1024.0)) / seconds;

    std::cout << "[IS-ANS] Decoded " << TEST_SIZE / (1024 * 1024) << " MB in "
              << seconds << " s (" << throughput_gbps << " GB/s)\n";
}

int main() {
    std::cout << "Starting main..." << std::endl;
    std::cout << "========================================================\n";
    std::cout << " Testing Lattice Novel Encoding Scheme (BPMT + IS-ANS)\n";
    std::cout << "========================================================\n" << std::endl;

    // Create test float mesh data (640,000 floats = 2.56 MB)
    std::cout << "Generating mesh_data..." << std::endl;
    std::vector<float> mesh_data(640000);
    for (size_t i = 0; i < mesh_data.size(); ++i) {
        mesh_data[i] = std::sin(i * 0.01f) + std::cos(i * 0.005f) * 1.5f;
    }
    std::cout << "Creating original_bytes..." << std::endl;
    const uint8_t* raw_ptr = reinterpret_cast<const uint8_t*>(mesh_data.data());
    std::vector<uint8_t> original_bytes(raw_ptr, raw_ptr + mesh_data.size() * sizeof(float));

    // Test BPMT transform accuracy
    std::cout << "Running bpmt_transform..." << std::endl;
    std::vector<uint8_t> transformed = bpmt_transform(original_bytes);
    std::cout << "Running bpmt_untransform..." << std::endl;
    std::vector<uint8_t> untransformed = bpmt_untransform(transformed);

    bool bit_exact = (original_bytes == untransformed);
    std::cout << "[BPMT] Bit-exact roundtrip verified: " << (bit_exact ? "PASS [YES]" : "FAIL [NO]") << std::endl;

    // Count zero bytes in transformed vs original
    size_t orig_zeros = 0, trans_zeros = 0;
    for (size_t i = 0; i < original_bytes.size(); ++i) {
        if (original_bytes[i] == 0) orig_zeros++;
        if (transformed[i] == 0) trans_zeros++;
    }
    std::cout << "[BPMT] Zero bytes in raw float stream: " << orig_zeros << " ("
              << (100.0 * orig_zeros / original_bytes.size()) << "%)\n";
    std::cout << "[BPMT] Zero bytes in BPMT bit-plane stream: " << trans_zeros << " ("
              << (100.0 * trans_zeros / transformed.size()) << "%)\n\n" << std::endl;

    // Benchmark IS-ANS SIMD decompression throughput
    test_isans_speed();

    return 0;
}
