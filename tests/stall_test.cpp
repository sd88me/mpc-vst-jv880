// Real-time checks of the audio path and the patch / bank controls (tests/stall.sh; needs your ROMs and, for most checks,
// expansion cards):
//   * a host block of 512 frames plays without the engine's ring running dry;
//   * picking patches on other expansion cards never holds up the audio callback (the engine's own thread loads the card), and a
//     state saved straight after such a pick never pairs the new patch number with the old patch's data;
//   * PATCH: a fast Q-Link turn moves one patch a tick, also across a pause and at the bottom of the range; a set to a value
//     (a direct set, 14-bit NRPN) goes to that value;
//   * the bank as a value (the bank name in the header LCD) steps one bank a tick;
//   * BANKS: a PATCH step after browsing starts in the bank on screen, a patch number next to the current one does not;
//   * patch tiles: a tile that was switched off fires again, only the loaded patch's tile is lit, and a tile is read back at once.
// The fake host keeps its own value for every parameter, as a real one does: it adopts what the plugin tells it
// (audioMasterAutomate), sends nothing when a control cannot move its value any further, and toggles a tile on a tap.
// processReplacing runs on its own thread, one block every block period; the plugin's own worker runs as on a device.
#include "mpc_vst2_abi.h"
#include "params_gen.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

extern "C" AEffect* VSTPluginMain(audioMasterCallback);
extern "C" int jv_dbg_ready(AEffect*);
extern "C" int jv_dbg_engine(AEffect*, const char*, char*, int);
extern "C" int jv_dbg_state(AEffect*, char*, int);

static int g_fail = 0;
#define CHECK(c, ...) do { if (c) { std::printf("  ok   "); } else { std::printf("  FAIL "); g_fail++; } std::printf(__VA_ARGS__); std::printf("\n"); } while (0)

static std::atomic<float> g_host[kNumParams];   // the host's own value of every parameter (normalised)
static std::atomic<int> g_told[kNumParams];     // how often the plugin told the host about it
static std::atomic<bool> g_adopt{true};         // false: the control keeps its own running value whatever the plugin tells the host

static VstIntPtr host(AEffect*, VstInt32 op, VstInt32 index, VstIntPtr, void*, float opt)
{
    if (op == audioMasterVersion) return 2400;
    if (op == audioMasterAutomate && index >= 0 && index < kNumParams) { if (g_adopt.load()) g_host[index] = opt; g_told[index]++; }
    return 0;
}

static int idx(const char* key)
{
    for (int i = 0; i < kNumParams; i++) if (!std::strcmp(g_pspecs[i].key, key)) return i;
    std::printf("no param %s\n", key); std::exit(2);
}
static float span(int i) { return g_pspecs[i].max - g_pspecs[i].min; }
static float norm(int i, float plain) { return span(i) > 0 ? (plain - g_pspecs[i].min) / span(i) : 0.f; }
static float hostPlain(int i) { return g_pspecs[i].min + g_host[i].load() * span(i); }
static std::string eng(AEffect* e, const char* k, int n = 256) { std::vector<char> b((size_t)n, 0); jv_dbg_engine(e, k, b.data(), n); return b.data(); }
static int engi(AEffect* e, const char* k) { return std::atoi(eng(e, k).c_str()); }
static std::string engState(AEffect* e) { std::vector<char> b(20000, 0); jv_dbg_state(e, b.data(), (int)b.size()); return b.data(); }
static void sleepMs(int ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }

// The host sets a parameter to a value. Nothing is sent when that is the value it already has.
static bool hostSet(AEffect* e, int i, float v)
{
    v = std::min(std::max(v, 0.0f), 1.0f);
    if (v == g_host[i].load()) return false;
    g_host[i] = v;
    e->setParameter(e, i, v);
    return true;
}
static bool hostSetPlain(AEffect* e, int i, float plain) { return hostSet(e, i, norm(i, plain)); }
// A Q-Link tick / wheel click: the host moves its own value by `stepPlain` (in the parameter's units), clamped to the range.
static bool tick(AEffect* e, int i, float stepPlain) { return hostSet(e, i, g_host[i].load() + stepPlain / span(i)); }
// A tap on a tile (a toggle Button): the host flips its own value.
static void tap(AEffect* e, int i) { hostSet(e, i, g_host[i].load() > 0.5f ? 0.0f : 1.0f); }

static const int kBlockFrames = 512;
static std::atomic<bool> g_quit{false};
static std::atomic<long> g_maxCallUs{0};     // the longest processReplacing call since it was last cleared
static std::mutex g_midiMu;
static std::vector<std::vector<uint8_t>> g_midi;   // 3-byte messages for the next block

static void midi(std::initializer_list<std::vector<uint8_t>> msgs)
{
    std::lock_guard<std::mutex> g(g_midiMu);
    for (const auto& m : msgs) g_midi.push_back(m);
}

static void audioThread(AEffect* e)
{
    std::vector<float> L(kBlockFrames), R(kBlockFrames);
    float* out[2] = {L.data(), R.data()};
    const auto period = std::chrono::nanoseconds((long long)(1e9 * kBlockFrames / 44100.0));
    auto next = std::chrono::steady_clock::now();
    while (!g_quit.load())
    {
        std::vector<std::vector<uint8_t>> msgs;
        { std::lock_guard<std::mutex> g(g_midiMu); msgs.swap(g_midi); }
        if (!msgs.empty())
        {
            std::vector<VstMidiEvent> ev(msgs.size());
            std::vector<char> buf(sizeof(VstEvents) + sizeof(VstEvent*) * msgs.size());
            VstEvents* evs = reinterpret_cast<VstEvents*>(buf.data());
            evs->numEvents = (VstInt32)msgs.size();
            for (size_t k = 0; k < msgs.size(); k++)
            {
                std::memset(&ev[k], 0, sizeof ev[k]);
                ev[k].type = kVstMidiType; ev[k].byteSize = sizeof(VstMidiEvent);
                for (size_t j = 0; j < 3 && j < msgs[k].size(); j++) ev[k].midiData[j] = (char)msgs[k][j];
                evs->events[k] = reinterpret_cast<VstEvent*>(&ev[k]);
            }
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

// The first 12 characters of the patch data in a saved state ("patch":"<hex>"), or "" when the state carries no patch data.
static std::string statePatchName(const std::string& state)
{
    const size_t p = state.find("\"patch\":\"");
    if (p == std::string::npos) return "";
    std::string name;
    for (int i = 0; i < 12; i++) name += (char)std::strtol(state.substr(p + 9 + (size_t)i * 2, 2).c_str(), nullptr, 16);
    return name;
}

int main(int argc, char** argv)
{
    const int PRESET = idx("preset");
    AEffect* e = VSTPluginMain(host);
    for (int i = 0; i < kNumParams; i++) { g_host[i] = e->getParameter(e, i); g_told[i] = 0; }
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
    const bool audioPath = !eng(e, "underruns").empty();   // the build with the audio-path changes (its own diagnostics key)
    const int total = engi(e, "total_patches"), banks = engi(e, "bank_count");
    const bool cards = total > 600 && banks >= 7;          // the checks below that need expansion cards
    if (!cards) std::printf("  --   %d patches in %d banks: the checks that need expansion cards are skipped\n", total, banks);

    midi({{0x90, 60, 100}});
    if (audioPath)
    {
        std::printf("== a %d-frame host block\n", kBlockFrames);
        sleepMs(500);
        const int u0 = engi(e, "underruns");
        sleepMs(4000);
        const int u1 = engi(e, "underruns");
        CHECK(u1 == u0, "4 s of %d-frame blocks: %d underruns", kBlockFrames, u1 - u0);
    }

    if (cards)
    {
        std::printf("== patches on other cards (%d patches)\n", total);
        g_maxCallUs = 0;
        const int serial0 = engi(e, "patch_serial");
        int picked = 0, badSaves = 0;
        for (int p = 300; p < total && picked < 12; p += 311, ++picked)   // each pick lands on another card
        {
            hostSetPlain(e, PRESET, (float)p);
            // a state saved while the card is still being read: no patch data, or the picked patch's (never the old patch's)
            const std::string st = engState(e), nm = statePatchName(st);
            if (st.find("\"preset\":" + std::to_string(p) + ",") == std::string::npos || (!nm.empty() && nm != eng(e, "patch_name"))) badSaves++;
            sleepMs(700);
        }
        const long worst = g_maxCallUs.load();
        if (audioPath) CHECK(worst < 20000, "%d card changes: the longest audio callback took %.1f ms", picked, worst / 1000.0);
        else std::printf("  --   %d card changes: the longest audio callback took %.1f ms\n", picked, worst / 1000.0);
        sleepMs(1500);
        const int last = 300 + 311 * (picked - 1);
        const std::string after = engState(e);
        CHECK(engi(e, "preset") == last && engi(e, "current_expansion") >= 0 && statePatchName(after) == eng(e, "patch_name"),
              "the last pick (%d) is loaded: card %d in the emulator, \"%s\" in the working patch", last, engi(e, "current_expansion"),
              statePatchName(after).c_str());
        if (audioPath) CHECK(engi(e, "patch_serial") >= serial0 + picked && badSaves == 0,
                             "%d patches reached the emulator; %d saves during a load had the wrong patch data", engi(e, "patch_serial") - serial0, badSaves);
    }

    std::printf("== PATCH: Q-Link turns\n");
    {
        hostSetPlain(e, PRESET, 10.0f);   // a direct set
        sleepMs(1200);
        const int start = engi(e, "preset");
        // the host's own value moves 37.3 patches a tick (a Q-Link's step on a 0..8191 range), 60 ticks, 8 ms apart
        for (int k = 0; k < 60; ++k) { tick(e, PRESET, 37.3f); sleepMs(8); }
        sleepMs(100);
        CHECK(start == 10 && engi(e, "preset") == start + 60, "60 fast ticks up: patch %d -> %d (one a tick)", start, engi(e, "preset"));
        // pauses around the worker's 300 ms hold, each followed by one tick: still one patch a tick
        for (int pause : {270, 295, 305, 320}) { sleepMs(pause); tick(e, PRESET, 37.3f); }
        sleepMs(100);
        CHECK(engi(e, "preset") == start + 64, "a tick after a pause of about 0.3 s: patch %d", engi(e, "preset"));
        sleepMs(600);   // the turn has rested: the host has the patch number again
        CHECK(std::lround(hostPlain(PRESET)) == start + 64 && g_told[PRESET] > 0, "the host was told the patch (%.0f)", hostPlain(PRESET));
        // down, 20 ms apart: the host's value hits the bottom of its range every third tick and gets the patch back
        const int from = engi(e, "preset");
        int sent = 0;
        for (int k = 0; k < 25; ++k) { sent += tick(e, PRESET, -37.3f) ? 1 : 0; sleepMs(20); }
        sleepMs(300);
        CHECK(sent >= 22 && engi(e, "preset") == from - sent, "25 ticks down at the bottom of the range: %d reached the plugin, patch %d -> %d",
              sent, from, engi(e, "preset"));
    }

    std::printf("== PATCH: a control that keeps its own value\n");
    {
        // As above, but the host does not take over the value the plugin tells it (a control with a running value of its
        // own): after a pause the next tick comes from where the control's value had got to, far from the patch.
        hostSetPlain(e, PRESET, 1000.0f);
        sleepMs(1200);
        g_adopt = false;
        const int start = engi(e, "preset");
        for (int k = 0; k < 80; ++k) { tick(e, PRESET, 37.3f); sleepMs(8); }     // the control's value is now about 3000 patches ahead
        for (int rest : {400, 350, 900})
        {
            sleepMs(rest);                                                         // the plugin tells the host the patch; the control ignores it
            for (int k = 0; k < 10; ++k) { tick(e, PRESET, 37.3f); sleepMs(8); }
        }
        sleepMs(100);
        const int up = engi(e, "preset");
        CHECK(start == 1000 && up == start + 110, "110 ticks up with three pauses: patch %d -> %d", start, up);
        sleepMs(500);
        for (int k = 0; k < 30; ++k) { tick(e, PRESET, -37.3f); sleepMs(8); }      // and back, after a pause
        sleepMs(100);
        CHECK(engi(e, "preset") == up - 30, "30 ticks down after a pause: patch %d", engi(e, "preset"));
        sleepMs(600);
        g_adopt = true;
        g_host[PRESET] = e->getParameter(e, PRESET);
    }

    std::printf("== PATCH: a set to a value\n");
    {
        hostSetPlain(e, PRESET, 500.0f);
        sleepMs(700);
        const int a = engi(e, "preset");
        hostSetPlain(e, PRESET, 0.0f);    // to the very bottom of the range, from far away: patch 0, not one step down
        sleepMs(700);
        CHECK(a == 500 && engi(e, "preset") == 0, "set to 500, then to 0: patch %d, %d", a, engi(e, "preset"));
        // 14-bit NRPN: parameter number = PATCH's index, data MSB 10 LSB 50 = 1330 / 16383 of 0..8191 = patch 665
        midi({{0xB0, 99, (uint8_t)(PRESET >> 7)}, {0xB0, 98, (uint8_t)(PRESET & 127)}, {0xB0, 6, 10}, {0xB0, 38, 50}});
        sleepMs(700);
        CHECK(engi(e, "preset") == 665 && std::lround(hostPlain(PRESET)) == 665, "NRPN data 10 / 50: patch %d (host %.0f)", engi(e, "preset"), hostPlain(PRESET));
        const int W = idx("nvram_tone_0_wavenumber");
        hostSetPlain(e, PRESET, 2.0f);    // an internal patch: the internal wave table has 129 waves
        sleepMs(1200);
        hostSetPlain(e, W, 2.0f);
        sleepMs(500);
        hostSet(e, W, 1.0f);              // the wave knob to the top: the last wave of the table, not one wave up
        sleepMs(500);
        CHECK(engi(e, "nvram_tone_0_wavenumber") > 100, "wave number to the top: wave %d", engi(e, "nvram_tone_0_wavenumber"));
    }

    if (cards)
    {
        std::printf("== the bank as a value (data wheel on the bank name)\n");
        const int BANK = idx("bank_select");
        hostSetPlain(e, PRESET, 3.0f);   // a patch in the first bank
        sleepMs(1200);
        const int b0 = engi(e, "bank_select");
        const float click = 0.012f * span(BANK);   // a wheel click: a small move of the host's value
        for (int k = 0; k < 3; ++k) { tick(e, BANK, click); sleepMs(60); }
        sleepMs(500);
        CHECK(b0 == 0 && engi(e, "bank_select") == 3 && engi(e, "preset") == 192,   // three 64-patch internal banks come first
              "3 clicks up: bank %d -> %d, on its first patch (%d)", b0, engi(e, "bank_select"), engi(e, "preset"));
        CHECK(std::lround(hostPlain(BANK)) == 3 && g_told[BANK] > 0, "the host was told the bank (%.0f)", hostPlain(BANK));
        for (int k = 0; k < 5; ++k) { tick(e, BANK, -click); sleepMs(60); }   // five clicks down from bank 3: stops at the first bank
        sleepMs(500);
        CHECK(engi(e, "bank_select") == 0, "5 clicks down: bank %d (%d banks)", engi(e, "bank_select"), banks);
        hostSetPlain(e, BANK, 5.0f);
        sleepMs(700);
        hostSetPlain(e, BANK, 0.0f);     // a set to the first bank from bank 6: bank 1, not one bank down
        sleepMs(700);
        CHECK(engi(e, "bank_select") == 0, "set to bank 6, then to bank 1: bank %d", engi(e, "bank_select") + 1);
        hostSetPlain(e, PRESET, 700.0f);   // PATCH moved elsewhere: BANK follows
        sleepMs(1500);
        CHECK(std::lround(hostPlain(BANK)) == engi(e, "bank_select") && engi(e, "bank_select") > 2,
              "after a patch pick the host's BANK is the patch's bank (%d)", engi(e, "bank_select"));

        std::printf("== BANKS page: browse a bank, then PATCH\n");
        const int BB = idx("browse_bank_index");
        hostSetPlain(e, PRESET, 3.0f);
        sleepMs(1200);
        hostSetPlain(e, BB, 5.0f);       // Q-Link 1: the lists show bank 6; nothing is loaded
        sleepMs(600);
        CHECK(engi(e, "preset") == 3 && engi(e, "browse_bank_index") == 5, "browsing bank 6 loads nothing (patch %d)", engi(e, "preset"));
        hostSetPlain(e, PRESET, 4.0f);   // a patch NUMBER next to the current one (RANDOM, a recalled value): that patch
        sleepMs(700);
        CHECK(engi(e, "preset") == 4 && engi(e, "browse_bank_index") == 0, "a set to patch 4 while browsing goes to patch %d", engi(e, "preset"));
        hostSetPlain(e, BB, 5.0f);
        sleepMs(600);
        int first = -1;
        for (int k = 0; k < 4; ++k)      // Q-Link 2: four ticks up on PATCH
        {
            tick(e, PRESET, 37.3f);
            sleepMs(40);
            if (k == 0) first = engi(e, "preset");
        }
        sleepMs(600);
        CHECK(engi(e, "bank_select") == 5 && engi(e, "browse_bank_index") == 5 && engi(e, "preset") == first + 3,
              "PATCH steps in the browsed bank: bank %d, patch %d then %d", engi(e, "bank_select") + 1, first, engi(e, "preset"));
    }

    std::printf("== BANKS page: patch tiles\n");
    {
        const int T1 = idx("patch_slot_1"), T2 = idx("patch_slot_2"), B1 = idx("bank_slot_1"), B2 = idx("bank_slot_2");
        tap(e, B1);                      // the lists show the first bank
        sleepMs(300);
        if (g_host[T1].load() > 0.5f) { tap(e, T2); sleepMs(400); }   // start with tile 1 unlit
        tap(e, T1);                      // tile 1, then tile 2, then tile 1 again
        sleepMs(400);
        const int p1 = engi(e, "preset");
        tap(e, T2);
        sleepMs(400);
        const int p2 = engi(e, "preset");
        tap(e, T1);
        sleepMs(400);
        CHECK(p2 == p1 + 1 && engi(e, "preset") == p1, "tile 1, tile 2, tile 1 again: patch %d, %d, %d", p1, p2, engi(e, "preset"));
        CHECK(g_host[T1].load() > 0.5f && g_host[T2].load() < 0.5f, "the host shows only tile 1 lit (tile 1 %.0f, tile 2 %.0f)",
              g_host[T1].load(), g_host[T2].load());
        tap(e, B2);                      // another bank in the lists: tile 1 is another patch now and no longer lit ...
        sleepMs(80);
        tap(e, T1);                      // ... so a tap on it, 80 ms later, loads that patch (the host had to be told in time)
        sleepMs(500);
        CHECK(engi(e, "preset") == p1 + 64 && engi(e, "bank_select") == 1, "bank tile 2, then patch tile 1 at once: patch %d", engi(e, "preset"));
    }

    midi({{0x80, 60, 0}});
    sleepMs(300);
    g_quit = true;
    audio.join();
    e->dispatcher(e, effMainsChanged, 0, 0, nullptr, 0);
    e->dispatcher(e, effClose, 0, 0, nullptr, 0);
    if (g_fail) { std::printf("FAILED: %d checks\n", g_fail); return 1; }
    std::printf("OK\n");
    return 0;
}
