#pragma once
#include <iostream>
#include <vector>
#include <queue>
#include <map>
#include <string>
#include <sstream>
#include <iomanip>
#include <functional>
#include <limits>

namespace rangecoder
{
    using range_t = uint64_t;
    using byte_t = uint8_t;

    class PModel
    {
    public:
        virtual range_t cum_freq(int index) const = 0;
        virtual range_t c_freq(int index) const = 0;
        range_t total_freq() const
        {
            return cum_freq(max_index()) + c_freq(max_index());
        };
        virtual int min_index() const = 0;
        virtual int max_index() const = 0;
        bool index_is_valid(int index)
        {
            return min_index() <= index && index <= max_index();
        }
    };

    enum RangeCoderVerbose {
        SILENT = false,
        VERBOSE = true,
    };

    namespace local
    {
        constexpr auto TOP8 = range_t(1) << (64 - 8);
        constexpr auto TOP16 = range_t(1) << (64 - 16);

        inline auto hex_zero_filled(range_t bytes) -> std::string
        {
            std::stringstream sformatter;
            sformatter << std::setfill('0') << std::setw(sizeof(range_t) * 2) << std::hex << bytes;
            return sformatter.str();
        }

        inline auto hex_zero_filled(byte_t byte) -> std::string
        {
            std::stringstream sformatter;
            sformatter << std::setfill('0') << std::setw(2) << std::hex << static_cast<int>(byte);
            return sformatter.str();
        }

        class RangeCoder
        {
        public:
            RangeCoder()
            {
                m_lower_bound = 0;
                m_range = std::numeric_limits<range_t>::max();
            };

            template<RangeCoderVerbose RANGECODER_VERBOSE>
            auto update_param(
                const PModel &pmodel, const int index, const std::function<void(byte_t)> &f = [](byte_t) {}) -> int
            {
                const auto c_freq = pmodel.c_freq(index);
                const auto cum_freq = pmodel.cum_freq(index);
                const auto total_freq = pmodel.total_freq();

                auto num_bytes = 0;

                const auto range_per_total = m_range / total_freq;
                m_range = range_per_total * c_freq;
                m_lower_bound += range_per_total * cum_freq;

                while (is_no_carry_expansion_needed())
                {
                    f(do_no_carry_expansion<RANGECODER_VERBOSE>());
                    num_bytes++;
                }
                while (is_range_reduction_expansion_needed())
                {
                    f(do_range_reduction_expansion<RANGECODER_VERBOSE>());
                    num_bytes++;
                }
                return num_bytes;
            };

            template<RangeCoderVerbose RANGECODER_VERBOSE>
            auto shift_byte() -> byte_t
            {
                auto tmp = static_cast<byte_t>(m_lower_bound >> (64 - 8));
                m_range <<= 8;
                m_lower_bound <<= 8;
                return tmp;
            };

        protected:
            void lower_bound(const range_t lower_bound) { m_lower_bound = lower_bound; }
            void range(const range_t range) { m_range = range; };
            auto lower_bound() const -> range_t { return m_lower_bound; };
            auto range() const -> range_t { return m_range; };
            auto upper_bound() const -> uint64_t { return m_lower_bound + m_range; };

        private:
            auto is_no_carry_expansion_needed() const -> bool
            {
                return (m_lower_bound ^ upper_bound()) < local::TOP8;
            };

            template<RangeCoderVerbose RANGECODER_VERBOSE>
            auto do_no_carry_expansion() -> byte_t
            {
                return shift_byte<RANGECODER_VERBOSE>();
            };

            auto is_range_reduction_expansion_needed() const -> bool
            {
                return m_range < local::TOP16;
            };

            template<RangeCoderVerbose RANGECODER_VERBOSE>
            auto do_range_reduction_expansion() -> byte_t
            {
                m_range = (~m_lower_bound) & (local::TOP16 - 1);
                return shift_byte<RANGECODER_VERBOSE>();
            };

            uint64_t m_lower_bound;
            uint64_t m_range;
        };
    }

    class RangeEncoder : local::RangeCoder
    {
    public:
        template<RangeCoderVerbose RANGECODER_VERBOSE = SILENT>
        auto encode(const PModel &pmodel, const int index) -> int
        {
            return update_param<RANGECODER_VERBOSE>(pmodel, index, [this](auto byte) { m_bytes.push_back(byte); });
        };

        template<RangeCoderVerbose RANGECODER_VERBOSE = SILENT>
        auto finish() -> std::vector<byte_t>
        {
            for (auto i = 0; i < 8; i++)
            {
                m_bytes.push_back(shift_byte<RANGECODER_VERBOSE>());
            }
            return m_bytes;
        }

    private:
        std::vector<uint8_t> m_bytes;
    };

    class RangeDecoder : local::RangeCoder
    {
    public:
        void start(const std::vector<byte_t> &bytes)
        {
            m_data = 0;
            for (auto byte : bytes)
            {
                m_bytes.push(byte);
            }
            lower_bound(0);
            range(std::numeric_limits<range_t>::max());

            for (auto i = 0; i < 8; i++)
            {
                shift_byte_buffer();
            }
        };

        template<RangeCoderVerbose RANGECODER_VERBOSE = SILENT>
        auto decode(const PModel &pmodel) -> int
        {
            const auto index = binary_search_encoded_index<RANGECODER_VERBOSE>(pmodel);
            const auto n = update_param<RANGECODER_VERBOSE>(pmodel, index);
            for (int i = 0; i < n; i++)
            {
                shift_byte_buffer();
            }
            return static_cast<int>(index);
        };

    private:
        template<RangeCoderVerbose RANGECODER_VERBOSE>
        auto binary_search_encoded_index(const PModel &pmodel) const -> int
        {
            auto left = pmodel.min_index();
            auto right = pmodel.max_index();
            const auto range_per_total = range() / pmodel.total_freq();
            const auto f = (m_data - lower_bound()) / range_per_total;

            while (left < right)
            {
                const auto mid = (left + right) / 2;
                const auto mid_cum = pmodel.cum_freq(mid + 1);

                if (mid_cum <= f)
                {
                    left = mid + 1;
                }
                else
                {
                    right = mid;
                }
            }
            return left;
        };

        void shift_byte_buffer()
        {
            if (m_bytes.empty()) {
                m_data = (m_data << 8);
                return;
            }
            const auto front_byte = m_bytes.front();
            m_data = (m_data << 8) | static_cast<range_t>(front_byte);
            m_bytes.pop();
        };

        std::queue<byte_t> m_bytes;
        range_t m_data;
    };

    template<int N = 256>
    class UniformDistribution : public PModel
    {
    public:
        UniformDistribution() = default;

        range_t c_freq(const int index) const override { return 1; }
        range_t cum_freq(const int index) const override { return index; }
        int min_index() const override { return 0; }
        int max_index() const override { return N - 1; }
    };
}
