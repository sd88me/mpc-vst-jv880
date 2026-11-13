// Real-time checks of the audio path (tests/stall.sh; needs your ROMs and, for the card checks, expansion cards):
//   * a host block of 512 frames plays without the engine's ring running dry;
//   * picking patches on other expansion cards never holds up the audio callback (the card is loaded by the engine's own thread);
//   * a fast Q-Link turn on PATCH moves one patch a tick, wherever the host's own value has run to.
// A fake host runs processReplacing on its own thread, one block every block period, and times every call.
#include "mpc_vst2_abi.h"
#include "params_gen.h"

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

extern "C" AEffect* VSTPluginMain(audioMasterCallback);
extern "C" int jv_dbg_ready(AEffect*);
extern "C" int jv_dbg_engine(AEffect*, const char*, char*, int);

static int g_fail = 0;
#define CHECK(c, ...) do { if (c) { std::printf("  ok   "); } else { std::printf("  FAIL "); g_fail++; } std::printf(__VA_ARGS__); std::printf("\n"); } while (0)

static VstIntPtr host(AEffect*, VstInt32 op, VstInt32, VstIntPtr, void*, float) { return op == audioMasterVersion ? 2400 : 0; }

static int idx(const char* key)
{
    for (int i = 0; i < kNumParams; i++) if (!std::strcmp(g_pspecs[i].key, key)) return i;
    std::printf("no param %s\n", key); std::exit(2);
}
static float norm(int i, float plain) { const PSpec& s = g_pspecs[i]; return s.max > s.min ? (plain - s.min) / (s.max - s.min) : 0.f; }
static std::string eng(AEffect* e, const char* k) { char b[256] = {0}; jv_dbg_engine(e, k, b, sizeof b); return b; }
static int engi(AEffect* e, const char* k) { return std::atoi(eng(e, k).c_str()); }
static void sleepMs(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

static const int kBlockFrames = 512;
static std::atomic<bool> g_quit{false};
static std::atomic<long> g_maxCallUs{0};     // the longest processReplacing call since it was last cleared
static std::atomic<int> g_noteOn{-1}, g_noteOff{-1};

static void audioThread(AEffect* e)
{
    std::vector<float> L(kBlockFrames), R(kBlockFrames);
    float* out[2] = {L.data(), R.data()};
    const auto period = std::chrono::nanoseconds((long long)(1e9 * kBlockFrames / 44100.0));
    auto next = std::chrono::steady_clock::now();
    while (!g_quit.load())
    {
        for (std::atomic<int>* n : {&g_noteOn, &g_noteOff})
        {
            const int note = n->exchange(-1);
            if (note < 0) continue;
            VstMidiEvent ev;
            std::memset(&ev, 0, sizeof ev);
            ev.type = kVstMidiType; ev.byteSize = sizeof(VstMidiEvent);
            ev.midiData[0] = (char)(n == &g_noteOn ? 0x90 : 0x80); ev.midiData[1] = (char)note; ev.midiData[2] = 100;
            char buf[sizeof(VstEvents) + sizeof(VstEvent*)];
            VstEvents* evs = reinterpret_cast<VstEvents*>(buf);
            evs->numEvents = 1; evs->events[0] = reinterpret_cast<VstEvent*>(&ev);
            e->dispatcher(e, effProcessEvents, 0, 0, evs, 0);
        }
        const auto t0 = std::chrono::steady_clock::now();
        e->processReplacing(e, nullptr, out, kBlockFrames);
        const long us = (long)std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - t0).count();
        long seen = g_maxCallUs.load();
        while (us > seen && !g_maxCallUs.compare_exchange_weak(seen, us)) {}
        next += period;
        std::this_thread::sleep_until(next);
    }
}

int main(int argc, char** argv)
{
    const int PRESET = idx("preset");
    AEffect* e = VSTPluginMain(host);
    e->dispatcher(e, effSetSampleRate, 0, 0, nullptr, 44100.f);
    e->dispatcher(e, effSetBlockSize, 0, kBlockFrames, nullptr, 0);
    e->dispatcher(e, effMainsChanged, 0, 1, nullptr, 0);
    std::thread audio(audioThread, e);

    for (int t = 0; t < 600 && !jv_dbg_ready(e); t++) sleepMs(100);
    if (argc > 1 && !std::strcmp(argv[1], "warm"))   // first start: scan the cards and write the patch cache, as a first run on a device
    {
        sleepMs(500);
        const bool ready = jv_dbg_ready(e) != 0;
        g_quit = true;
        audio.join();
        e->dispatcher(e, effMainsChanged, 0, 0, nullptr, 0);
        e->dispatcher(e, effClose, 0, 0, nullptr, 0);
        return ready ? 0 : 1;
    }
    CHECK(jv_dbg_ready(e), "ROMs loaded (%s)", eng(e, "loading_status").c_str());
    sleepMs(1500);
    const bool hasCounter = !eng(e, "underruns").empty();
    const int total = engi(e, "total_patches");

    std::printf("== a %d-frame host block\n", kBlockFrames);
    g_noteOn = 60;
    sleepMs(500);
    const int u0 = engi(e, "underruns");
    sleepMs(4000);
    const int u1 = engi(e, "underruns");
    if (hasCounter) CHECK(u1 == u0, "4 s of %d-frame blocks: %d underruns", kBlockFrames, u1 - u0);
    else std::printf("  --   this build has no underrun counter\n");

    std::printf("== patches on other cards (%d patches)\n", total);
    if (total > 600)
    {
        g_maxCallUs = 0;
        int picked = 0;
        for (int p = 300; p < total && picked < 12; p += 311, ++picked)   // each pick lands on another card
        {
            e->setParameter(e, PRESET, norm(PRESET, (float)p));
            sleepMs(700);
        }
        const long worst = g_maxCallUs.load();
        CHECK(worst < 20000, "%d card changes: the longest audio callback took %.1f ms", picked, worst / 1000.0);
        sleepMs(1500);
        CHECK(engi(e, "preset") == 300 + 311 * (picked - 1), "the last pick is the current patch (%d)", engi(e, "preset"));
    }
    else std::printf("  --   no expansion cards in the ROM folder\n");

    std::printf("== a fast Q-Link turn on PATCH\n");
    {
        e->setParameter(e, PRESET, norm(PRESET, 10.0f));   // a direct set
        sleepMs(1200);
        const int start = engi(e, "preset");
        // the host's own value moves 37.3 patches a tick (a Q-Link's step on a 0..8191 range), 60 ticks, 8 ms apart
        float host = (float)start;
        for (int k = 0; k < 60; ++k)
        {
            host += 37.3f;
            e->setParameter(e, PRESET, norm(PRESET, host));
            sleepMs(8);
        }
        sleepMs(300);
        CHECK(start == 10 && engi(e, "preset") == start + 60, "60 ticks up: patch %d -> %d (one a tick)", start, engi(e, "preset"));
        sleepMs(600);   // the turn has rested: the host's value is the patch again
        float back = (float)engi(e, "preset");
        for (int k = 0; k < 25; ++k)
        {
            back -= 37.3f;
            e->setParameter(e, PRESET, norm(PRESET, back));
            sleepMs(8);
        }
        sleepMs(300);
        CHECK(engi(e, "preset") == start + 60 - 25, "25 ticks down: patch %d", engi(e, "preset"));
    }

    std::printf("== the bank as a value (data wheel on the bank name)\n");
    {
        const int BANK = idx("bank_select"), banks = engi(e, "bank_count");
        e->setParameter(e, PRESET, norm(PRESET, 3.0f));   // a patch in the first bank
        sleepMs(1200);
        const int b0 = engi(e, "bank_select");
        float host = e->getParameter(e, BANK);
        for (int k = 0; k < 3; ++k)   // three wheel clicks up, each a small move of the host's value, 60 ms apart
        {
            host += 0.012f;
            e->setParameter(e, BANK, host);
            sleepMs(60);
        }
        sleepMs(500);
        CHECK(b0 == 0 && engi(e, "bank_select") == 3 && engi(e, "preset") == 192,   // three 64-patch internal banks come first
              "3 clicks up: bank %d -> %d, on its first patch (%d)", b0, engi(e, "bank_select"), engi(e, "preset"));
        CHECK(std::lround(e->getParameter(e, BANK) * 21.0f) == 3, "the host's BANK value follows (%.0f)", e->getParameter(e, BANK) * 21.0f);
        host = e->getParameter(e, BANK);
        for (int k = 0; k < 5; ++k)   // five clicks down from bank 3: stops at the first bank
        {
            host = std::max(0.0f, host - 0.012f);
            e->setParameter(e, BANK, host);
            sleepMs(60);
        }
        sleepMs(500);
        CHECK(engi(e, "bank_select") == 0, "5 clicks down: bank %d (%d banks)", engi(e, "bank_select"), banks);
        e->setParameter(e, PRESET, norm(PRESET, 700.0f));   // PATCH moved elsewhere: BANK follows
        sleepMs(1500);
        CHECK(std::lround(e->getParameter(e, BANK) * 21.0f) == engi(e, "bank_select") && engi(e, "bank_select") > 2,
              "after a patch pick the host's BANK is the patch's bank (%d)", engi(e, "bank_select"));
    }

    std::printf("== BANKS page: browse a bank, then turn PATCH\n");
    {
        const int BB = idx("browse_bank_index");
        e->setParameter(e, PRESET, norm(PRESET, 3.0f));
        sleepMs(1200);
        e->setParameter(e, BB, norm(BB, 5.0f));   // Q-Link 1: the lists show bank 6; nothing is loaded
        sleepMs(600);
        CHECK(engi(e, "preset") == 3 && engi(e, "browse_bank_index") == 5, "browsing bank 6 loads nothing (patch %d)", engi(e, "preset"));
        float host = e->getParameter(e, PRESET);
        int first = -1;
        for (int k = 0; k < 4; ++k)               // Q-Link 2: four ticks up on PATCH
        {
            host += 37.3f / 8191.0f;
            e->setParameter(e, PRESET, host);
            sleepMs(40);
            if (k == 0) first = engi(e, "preset");
        }
        sleepMs(600);
        CHECK(engi(e, "bank_select") == 5 && engi(e, "browse_bank_index") == 5 && engi(e, "preset") == first + 3,
              "PATCH steps in the browsed bank: bank %d, patch %d then %d", engi(e, "bank_select") + 1, first, engi(e, "preset"));
    }

    std::printf("== BANKS page: patch tiles\n");
    {
        const int T1 = idx("patch_slot_1"), T2 = idx("patch_slot_2"), BB = idx("browse_bank_index");
        e->setParameter(e, BB, norm(BB, 0.0f));
        sleepMs(300);
        e->setParameter(e, T1, 1.0f);   // tap tile 1, then tile 2, then tile 1 again (the host only ever sends 1 for an unlit tile)
        sleepMs(400);
        const int p1 = engi(e, "preset");
        e->setParameter(e, T2, 1.0f);
        sleepMs(400);
        const int p2 = engi(e, "preset");
        e->setParameter(e, T1, 1.0f);
        sleepMs(400);
        CHECK(p2 == p1 + 1 && engi(e, "preset") == p1, "tile 1, tile 2, tile 1 again: patch %d, %d, %d", p1, p2, engi(e, "preset"));
        CHECK(e->getParameter(e, T1) > 0.5f && e->getParameter(e, T2) < 0.5f, "only tile 1 is lit (tile 1 %.0f, tile 2 %.0f)",
              e->getParameter(e, T1), e->getParameter(e, T2));
    }

    g_noteOff = 60;
    sleepMs(300);
    g_quit = true;
    audio.join();
    e->dispatcher(e, effMainsChanged, 0, 0, nullptr, 0);
    e->dispatcher(e, effClose, 0, 0, nullptr, 0);
    if (g_fail) { std::printf("FAILED: %d checks\n", g_fail); return 1; }
    std::printf("OK\n");
    return 0;
}
