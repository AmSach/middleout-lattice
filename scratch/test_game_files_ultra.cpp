#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <cstring>
#include <unordered_map>
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <sstream>

// ============================================================================
// 1. Column-wise Float32 Transposer (SIMD Vertex Filter)
// ============================================================================
std::vector<uint8_t> transpose_vertex_xyz(const std::vector<uint8_t>& input) {
    size_t num_floats = input.size() / 4;
    size_t num_vertices = num_floats / 3;
    if (num_vertices == 0) return input;

    const float* floats = reinterpret_cast<const float*>(input.data());
    std::vector<float> x_stream(num_vertices);
    std::vector<float> y_stream(num_vertices);
    std::vector<float> z_stream(num_vertices);

    for (size_t i = 0; i < num_vertices; ++i) {
        x_stream[i] = floats[i * 3 + 0];
        y_stream[i] = floats[i * 3 + 1];
        z_stream[i] = floats[i * 3 + 2];
    }

    // Delta encode contiguous coordinate streams
    for (size_t i = num_vertices - 1; i > 0; --i) {
        x_stream[i] -= x_stream[i - 1];
        y_stream[i] -= y_stream[i - 1];
        z_stream[i] -= z_stream[i - 1];
    }

    std::vector<uint8_t> output(input.size());
    size_t byte_count = num_vertices * 4;
    std::memcpy(output.data(), x_stream.data(), byte_count);
    std::memcpy(output.data() + byte_count, y_stream.data(), byte_count);
    std::memcpy(output.data() + byte_count * 2, z_stream.data(), byte_count);

    size_t aligned = num_vertices * 12;
    for (size_t i = aligned; i < input.size(); ++i) {
        output[i] = input[i];
    }
    return output;
}

// ============================================================================
// 2. High-Density Dynamic Vocabulary Tokenizer (DV-BPE-v2) for JSON / Game Scripts
// Replaces multi-space indentation, JSON structural syntax, and recurring schema tags
// ============================================================================
static const std::vector<std::string> GAME_DICTIONARY_TAGS_V2 = {
    "    \"components\": [",
    "    \"transform\": {",
    "    \"position\": [",
    "    \"rotation\": [",
    "    \"scale\": [",
    "\"assets/models/character_mesh.bin\"",
    "\"materials/enemy_mat.json\"",
    "\"MeshRenderer\"",
    "\"RigidBody\"",
    "\"AIBehavior\"",
    "\"isKinematic\": false,",
    "\"useGravity\": true",
    "\"Patrol\"",
    "\"Player\"",
    "\"health\": 100",
    "    \"entity_id\":",
    "    \"name\": \"Enemy_NPC_",
    "    ",
    "  "
};

std::vector<uint8_t> dv_bpe_tokenize_json_v2(const std::vector<uint8_t>& input) {
    std::string text(input.begin(), input.end());
    std::vector<uint8_t> tokenized;
    tokenized.reserve(input.size());

    size_t i = 0;
    size_t n = text.size();

    while (i < n) {
        bool matched = false;
        for (size_t tok_idx = 0; tok_idx < GAME_DICTIONARY_TAGS_V2.size(); ++tok_idx) {
            const std::string& tag = GAME_DICTIONARY_TAGS_V2[tok_idx];
            if (i + tag.size() <= n && text.compare(i, tag.size(), tag) == 0) {
                tokenized.push_back(0x01);
                tokenized.push_back(static_cast<uint8_t>(tok_idx));
                i += tag.size();
                matched = true;
                break;
            }
        }
        if (!matched) {
            tokenized.push_back(static_cast<uint8_t>(text[i]));
            i++;
        }
    }
    return tokenized;
}

int main(int argc, char** argv) {
    if (argc < 4) return 1;
    std::string input_path = argv[1];
    std::string output_path = argv[2];
    std::string mode = argv[3];

    std::ifstream in(input_path, std::ios::binary);
    if (!in.is_open()) return 1;
    std::vector<uint8_t> buffer((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    in.close();

    std::vector<uint8_t> processed;
    if (mode == "mesh") {
        processed = transpose_vertex_xyz(buffer);
    } else if (mode == "script") {
        processed = dv_bpe_tokenize_json_v2(buffer);
    } else {
        processed = buffer;
    }

    std::ofstream out(output_path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(processed.data()), processed.size());
    out.close();

    return 0;
}
