// Offline, deterministic render of the emulator core (src/dsp/mcu*.cpp + pcm.cpp, no threads, no plugin layer): a fixed MIDI
// script on a set of internal and expansion-card patches, one FNV-1a hash of the int16 output per scenario. A change to the core
// that is meant to keep the sound must leave every hash as it was (tests/core_hash.sh compares with a saved baseline).
// It also prints how long the render took, as a rough speed figure for this computer.
//
//   core_hash <roms dir> [seconds-scale]
// <roms dir> holds the five jv880_*.bin files and, optionally, expansions/SR-JV80-*.bin (as the plugin's jv880-roms/roms).

#include "../src/dsp/mcu.h"

#include <dirent.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
#include <string>
#include <vector>

void unscramble(const uint8_t* src, uint8_t* dst, const int len);   // src/dsp/mcu.cpp

namespace {

// as src/dsp/jv880_plugin.cpp
const int kPatchSize = 0x16a;
const int kNvramPatch = 0x0d70, kNvramMode = 0x11;
const uint32_t kPresetA = 0x010ce0, kPresetB = 0x018ce0, kInternal = 0x008ce0;
const int kCard8 = 0x800000, kCard2 = 0x200000;

bool readFile(const std::string& path, std::vector<uint8_t>& out, size_t want)
{
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    out.assign(want, 0);
    const size_t n = std::fread(out.data(), 1, want, f);
    std::fclose(f);
    return n == want;
}

long fileSize(const std::string& path)
{
    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return -1;
    std::fseek(f, 0, SEEK_END);
    const long n = std::ftell(f);
    std::fclose(f);
    return n;
}

struct Hash
{
    uint64_t h = 1469598103934665603ull;
    long nonzero = 0;
    int peak = 0;
    long frames = 0;
    void add(const int16_t* s, int n)   // n int16 values (stereo interleaved)
    {
        for (int i = 0; i < n; ++i)
        {
            const uint16_t v = (uint16_t)s[i];
            h = (h ^ (v & 0xff)) * 1099511628211ull;
            h = (h ^ (v >> 8)) * 1099511628211ull;
            if (s[i]) ++nonzero;
            peak = std::max(peak, std::abs((int)s[i]));
        }
        frames += n / 2;
    }
};

struct Runner
{
    MCU* m = nullptr;
    Hash* hash = nullptr;

    void midi(std::initializer_list<int> bytes)
    {
        uint8_t b[8];
        int n = 0;
        for (int v : bytes) b[n++] = (uint8_t)v;
        m->postMidiSC55(b, n);
    }

    // The plugin's emulator thread: updateSC55(64) = 32 stereo frames at 64 kHz a call.
    void run(double seconds)
    {
        const long calls = (long)(seconds * 64000.0 / 32.0);
        for (long i = 0; i < calls; ++i)
        {
            m->updateSC55(64);
            if (hash) hash->add(m->sample_buffer, m->sample_write_ptr);
        }
    }

    void warm(int n) { for (int i = 0; i < n; ++i) m->updateSC55(1); }
};

} // namespace

int main(int argc, char** argv)
{
    if (argc < 2) { std::fprintf(stderr, "usage: core_hash <roms dir> [time scale]\n"); return 2; }
    const std::string dir = argv[1];
    const double scale = argc > 2 ? std::atof(argv[2]) : 1.0;

    std::vector<uint8_t> rom1, rom2, wave1, wave2, nvram;
    if (!readFile(dir + "/jv880_rom1.bin", rom1, ROM1_SIZE) || !readFile(dir + "/jv880_rom2.bin", rom2, ROM2_SIZE) ||
        !readFile(dir + "/jv880_waverom1.bin", wave1, 0x200000) || !readFile(dir + "/jv880_waverom2.bin", wave2, 0x200000))
    {
        std::fprintf(stderr, "core_hash: the four JV-880 ROM files are not in %s\n", dir.c_str());
        return 2;
    }
    if (!readFile(dir + "/jv880_nvram.bin", nvram, NVRAM_SIZE)) nvram.assign(NVRAM_SIZE, 0xff);

    // Zeroed storage: the core leaves some arrays unset until the firmware writes them, and the render must not depend on that.
    void* mem = std::calloc(1, sizeof(MCU));
    if (!mem) return 2;
    MCU* m = new (mem) MCU();
    m->startSC55(rom1.data(), rom2.data(), wave1.data(), wave2.data(), nvram.data());
    m->nvram[kNvramMode] = 1;   // patch mode

    // Expansion cards, by file name. Each gives two scenarios (its first patch and one from the middle).
    std::vector<std::string> cards;
    if (DIR* d = opendir((dir + "/expansions").c_str()))
    {
        while (dirent* e = readdir(d))
        {
            const std::string n = e->d_name;
            if (n.size() > 4 && n.find("SR-JV80") != std::string::npos && n.substr(n.size() - 4) == ".bin") cards.push_back(n);
        }
        closedir(d);
    }
    std::sort(cards.begin(), cards.end());

    struct Scenario { std::string id; int card; uint32_t offset; };   // card -1 = internal (offset into rom2)
    std::vector<Scenario> list = {
        {"presetA-00", -1, kPresetA + 0 * kPatchSize},  {"presetA-21", -1, kPresetA + 21 * kPatchSize},
        {"presetA-47", -1, kPresetA + 47 * kPatchSize}, {"presetB-09", -1, kPresetB + 9 * kPatchSize},
        {"presetB-38", -1, kPresetB + 38 * kPatchSize}, {"internal-05", -1, kInternal + 5 * kPatchSize},
    };
    std::vector<std::vector<uint8_t>> cardData(cards.size());
    for (size_t c = 0; c < cards.size(); ++c)
    {
        const std::string path = dir + "/expansions/" + cards[c];
        const long size = fileSize(path);
        std::vector<uint8_t> raw;
        if ((size != kCard8 && size != kCard2) || !readFile(path, raw, (size_t)size)) continue;
        cardData[c].assign((size_t)size, 0);
        unscramble(raw.data(), cardData[c].data(), (int)size);
        const uint8_t* u = cardData[c].data();
        const int count = u[0x67] | (u[0x66] << 8);
        const uint32_t off = u[0x8f] | (u[0x8e] << 8) | (u[0x8d] << 16) | ((uint32_t)u[0x8c] << 24);
        if (count <= 0 || count > 256 || (uint64_t)off + (uint64_t)count * kPatchSize > (uint64_t)size) { cardData[c].clear(); continue; }
        const std::string tag = cards[c].substr(0, cards[c].size() - 4);
        list.push_back({tag + "-first", (int)c, off});
        list.push_back({tag + "-mid", (int)c, off + (uint32_t)(count / 2) * kPatchSize});
    }

    Runner r;
    r.m = m;
    r.warm(100000);   // the plugin's start-up warm-up

    Hash total;
    int current = -1;
    double renderSeconds = 0, audioSeconds = 0;
    for (const Scenario& s : list)
    {
        if (s.card >= 0 && s.card != current)   // as v2_load_expansion_to_emulator: ROM in, card RAM, reset, short warm-up
        {
            const std::vector<uint8_t>& u = cardData[(size_t)s.card];
            std::memset(m->pcm.waverom_exp, 0, sizeof m->pcm.waverom_exp);
            std::memcpy(m->pcm.waverom_exp, u.data(), u.size());
            std::memset(m->cardram, 0, CARDRAM_SIZE);
            const int count = u[0x67] | (u[0x66] << 8);
            const uint32_t off = u[0x8f] | (u[0x8e] << 8) | (u[0x8d] << 16) | ((uint32_t)u[0x8c] << 24);
            const int bytes = std::min(std::min(count, 64) * kPatchSize, (int)CARDRAM_SIZE);
            std::memcpy(m->cardram, u.data() + off, (size_t)bytes);
            current = s.card;
            m->SC55_Reset();
            r.warm(1000);
        }
        const uint8_t* patch = s.card >= 0 ? cardData[(size_t)s.card].data() + s.offset : rom2.data() + s.offset;
        std::memcpy(&m->nvram[kNvramPatch], patch, (size_t)kPatchSize);
        m->nvram[kNvramMode] = 1;

        Hash h;
        r.hash = &h;
        const auto t0 = std::chrono::steady_clock::now();
        r.midi({0xC0, 0x00});                       // reload the working patch from NVRAM
        r.run(0.30 * scale);
        r.midi({0x90, 60, 100});                    // one note
        r.run(0.40 * scale);
        r.midi({0x90, 48, 90}); r.midi({0x90, 64, 110}); r.midi({0x90, 67, 70});   // a chord builds up
        r.run(0.30 * scale);
        r.midi({0xB0, 1, 96});                      // modulation
        r.midi({0xE0, 0, 0x50});                    // bend up
        r.run(0.30 * scale);
        r.midi({0x90, 36, 127}); r.midi({0x90, 72, 60}); r.midi({0x90, 79, 100}); r.midi({0x90, 84, 40});   // 8 notes
        r.run(0.50 * scale);
        r.midi({0xE0, 0, 0x40}); r.midi({0xB0, 1, 0});
        r.midi({0xB0, 64, 127});                    // sustain pedal, then release the keys
        for (int n : {60, 48, 64, 67, 36, 72, 79, 84}) r.midi({0x80, n, 64});
        r.run(0.40 * scale);
        r.midi({0xB0, 64, 0});
        r.run(0.80 * scale);                        // release tail
        r.midi({0xB0, 123, 0});
        r.run(0.20 * scale);
        const double took = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        r.hash = nullptr;

        renderSeconds += took;
        audioSeconds += (double)h.frames / 64000.0;
        std::printf("%-34s %016llx  peak %5d  nonzero %ld\n", s.id.c_str(), (unsigned long long)h.h, h.peak, h.nonzero);
        total.h = (total.h ^ h.h) * 1099511628211ull;
        total.nonzero += h.nonzero;
    }
    std::printf("%-34s %016llx\n", "TOTAL", (unsigned long long)total.h);
    std::fprintf(stderr, "core_hash: %zu scenarios, %.1f s of audio in %.2f s (%.1fx real time on this computer)\n",
                 list.size(), audioSeconds, renderSeconds, renderSeconds > 0 ? audioSeconds / renderSeconds : 0.0);
    m->~MCU();
    std::free(mem);
    return total.nonzero > 0 ? 0 : 1;
}
