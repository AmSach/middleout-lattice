/**
 * @file lattice_cli.cpp
 * @brief Middleout-Lattice CLI — Command-line interface for compression/decompression.
 *
 * Outputs JSON progress to stdout for Electron frontend integration.
 * Patent-pending technology. See lattice_engine.h for claim mapping.
 *
 * @copyright 2024-2026 Middleout-Lattice Project. All rights reserved.
 */

#include "lattice_engine.h"
#include <iostream>
#include <string>
#include <cstring>

static void print_json_status(const std::string& status) {
    std::cout << "{\"type\":\"status\",\"status\":\"" << status << "\"}" << std::endl;
}

static void print_json_progress(uint64_t processed, uint64_t total,
                                 const std::string& file) {
    double pct = (total > 0) ? (100.0 * processed / total) : 0.0;
    std::cout << "{\"type\":\"progress\",\"bytes_processed\":" << processed
              << ",\"total\":" << total
              << ",\"percent\":" << pct
              << ",\"file\":\"" << file << "\"}" << std::endl;
}

static void print_json_done(const lattice::CompressResult& r) {
    std::cout << "{\"type\":\"done\""
              << ",\"original_size\":" << r.total_original
              << ",\"compressed_size\":" << r.total_compressed
              << ",\"ratio\":" << r.ratio
              << ",\"elapsed\":" << r.elapsed_seconds
              << ",\"throughput_mbps\":" << r.throughput_mbps
              << ",\"file_count\":" << r.num_files
              << "}" << std::endl;
}

static void print_json_error(const std::string& msg) {
    std::cout << "{\"type\":\"error\",\"message\":\"" << msg << "\"}" << std::endl;
}

static void print_usage() {
    std::cerr << "Middleout-Lattice Compression Engine v1.0\n"
              << "Patent-Pending High-Speed AI Model Compressor\n\n"
              << "Usage:\n"
              << "  lattice_cli compress <input> <output> [--virtually-lossless [level]] [--solid]\n"
              << "  lattice_cli decompress <archive> <dest_dir>\n"
              << "  lattice_cli info <archive>\n\n"
              << "Options:\n"
              << "  --virtually-lossless, --vl [level]  Zero lowest mantissa bytes (Patent Claim 4)\n"
              << "                                      level 1 (default): mask 1 byte (MSE ~1e-14)\n"
              << "                                      level 2: mask 2 bytes (MSE ~1e-9)\n"
              << "                                      level 3: mask 3 bytes (MSE ~1e-4)\n"
              << "  --solid                             Share dictionary across files\n"
              << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        print_usage();
        return 1;
    }

    std::string command = argv[1];

    if (command == "compress") {
        if (argc < 4) {
            print_json_error("Usage: lattice_cli compress <input> <output> [--virtually-lossless] [--solid]");
            return 1;
        }

        const char* input_path  = argv[2];
        const char* output_path = argv[3];
        int vl   = 0;
        bool solid = false;
        bool fast = false;
        bool best = false;

        for (int i = 4; i < argc; i++) {
            if (std::strcmp(argv[i], "--virtually-lossless") == 0 || std::strcmp(argv[i], "--vl") == 0) {
                vl = 1;
                if (i + 1 < argc && argv[i+1][0] != '-') {
                    vl = std::atoi(argv[i+1]);
                    i++;
                }
            }
            else if (std::strcmp(argv[i], "--solid") == 0) solid = true;
            else if (std::strcmp(argv[i], "--fast") == 0) fast = true;
            else if (std::strcmp(argv[i], "--best") == 0) best = true;
        }

        print_json_status("loading_engine");

        lattice::LatticeEngine engine;
        engine.set_progress_callback([](uint64_t processed, uint64_t total,
                                        const std::string& file) {
            print_json_progress(processed, total, file);
        });

        print_json_status("initializing_compression");
        auto result = engine.compress(input_path, output_path, vl, solid, fast, best);

        if (result.success) {
            print_json_done(result);
            return 0;
        } else {
            print_json_error(result.error_message);
            return 1;
        }

    } else if (command == "decompress") {
        if (argc < 4) {
            print_json_error("Usage: lattice_cli decompress <archive> <dest_dir>");
            return 1;
        }

        const char* archive_path = argv[2];
        const char* dest_dir     = argv[3];

        print_json_status("loading_engine");

        lattice::LatticeEngine engine;
        engine.set_progress_callback([](uint64_t processed, uint64_t total,
                                        const std::string& file) {
            print_json_progress(processed, total, file);
        });

        print_json_status("initializing_decompression");
        auto result = engine.decompress(archive_path, dest_dir);

        if (result.success) {
            print_json_done(result);
            return 0;
        } else {
            print_json_error(result.error_message);
            return 1;
        }

    } else {
        print_usage();
        return 1;
    }
}
