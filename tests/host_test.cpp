// Offline host test for the SDK front end (src/JV880Plugin.cpp) with the real engine and ROMs, under ASan/UBSan (tests/run.sh).
// A fake VST2 host drives it in real time (the engine's emulator thread fills its ring at its own pace): identity, sound, value / choice /
// momentary / step / tile / read-only params, the parameter-0 nudge, CC and NRPN control, a state round trip into a second instance,
// a 1.0.9 project chunk (tests/data/legacy-1.0.9.chunk, made by the released build itself), a save before the ROMs are loaded, bad chunks.
// Prints OK at the end, or the failed checks and exits 1.
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
extern "C" void jv_dbg_tick(AEffect*);
extern "C" int jv_dbg_ready(AEffect*);
extern "C" int jv_dbg_engine(AEffect*, const char*, char*, int);
extern "C" void jv_dbg_engine_set(AEffect*, const char*, const char*);

static std::atomic<int> g_automate[kNumParams];
static std::atomic<int> g_updateDisplay{0};
static int g_fail = 0;

static VstIntPtr host(AEffect*, VstInt32 op, VstInt32 idx, VstIntPtr, void*, float)
{
    if (op == audioMasterAutomate && idx >= 0 && idx < kNumParams) g_automate[idx]++;
    if (op == audioMasterVersion) return 2400;
    if (op == audioMasterUpdateDisplay) g_updateDisplay++;
    return 0;
}

#define CHECK(c, ...) do { if (c) { std::printf("  ok   "); } else { std::printf("  FAIL "); g_fail++; } std::printf(__VA_ARGS__); std::printf("\n"); } while (0)

static int idx(const char* key)
{
    for (int i = 0; i < kNumParams; i++) if (!std::strcmp(g_pspecs[i].key, key)) return i;
    std::printf("no param %s\n", key); std::exit(2);
}
static float norm(int i, float plain) { const PSpec& s = g_pspecs[i]; return s.max > s.min ? (plain - s.min) / (s.max - s.min) : 0.f; }
static float plainOf(AEffect* e, int i) { const PSpec& s = g_pspecs[i]; return s.min + e->getParameter(e, i) * (s.max - s.min); }
static std::string eng(AEffect* e, const char* k) { char b[256]; jv_dbg_engine(e, k, b, sizeof b); return b; }
static int engi(AEffect* e, const char* k) { return std::atoi(eng(e, k).c_str()); }
static std::string disp(AEffect* e, int i) { char b[128] = {0}; e->dispatcher(e, effGetParamDisplay, i, 0, b, 0); return b; }

static double g_rms;
static void run(AEffect* e, int blocks, const std::vector<std::vector<uint8_t>>& midi = {})
{
    float L[128], R[128], *out[2] = {L, R};
    double acc = 0; long n = 0;
    for (int b = 0; b < blocks; b++)
    {
        if (b == 0 && !midi.empty())
        {
            std::vector<VstMidiEvent> ev(midi.size());
            std::vector<char> buf(sizeof(VstEvents) + sizeof(VstEvent*) * midi.size());
            VstEvents* evs = reinterpret_cast<VstEvents*>(buf.data());
            evs->numEvents = (VstInt32)midi.size();
            for (size_t k = 0; k < midi.size(); k++)
            {
                std::memset(&ev[k], 0, sizeof ev[k]);
                ev[k].type = kVstMidiType; ev[k].byteSize = sizeof(VstMidiEvent);
                for (size_t j = 0; j < 3 && j < midi[k].size(); j++) ev[k].midiData[j] = (char)midi[k][j];
                evs->events[k] = reinterpret_cast<VstEvent*>(&ev[k]);
            }
            e->dispatcher(e, effProcessEvents, 0, 0, evs, 0);
        }
        e->processReplacing(e, nullptr, out, 128);
        for (int i = 0; i < 128; i++) { acc += (double)L[i] * L[i] + (double)R[i] * R[i]; n += 2; }
        std::this_thread::sleep_for(std::chrono::microseconds(2900));
    }
    g_rms = n ? std::sqrt(acc / n) : 0;
}
static void settle(AEffect* e, int blocks = 40) { run(e, blocks); jv_dbg_tick(e); }

static AEffect* open(const char* what)
{
    AEffect* e = VSTPluginMain(host);
    e->dispatcher(e, effSetSampleRate, 0, 0, nullptr, 44100.f);
    e->dispatcher(e, effSetBlockSize, 0, 128, nullptr, 0);
    e->dispatcher(e, effMainsChanged, 0, 1, nullptr, 0);
    std::printf("%s: opened\n", what);
    return e;
}
static bool waitReady(AEffect* e)
{
    for (int t = 0; t < 400 && !jv_dbg_ready(e); t++) run(e, 34);   // up to ~40 s (ROM load + patch scan)
    run(e, 100);
    jv_dbg_tick(e);
    return jv_dbg_ready(e);
}
static std::vector<uint8_t> chunk(AEffect* e)
{
    void* p = nullptr;
    const VstIntPtr n = e->dispatcher(e, effGetChunk, 0, 0, &p, 0);
    return n > 0 && p ? std::vector<uint8_t>((uint8_t*)p, (uint8_t*)p + n) : std::vector<uint8_t>();
}

int main(int argc, char** argv)
{
    const char* legacyPath = argc > 1 ? argv[1] : "tests/data/legacy-1.0.9.chunk";
    const int P_LVL = idx("nvram_patchCommon_patchlevel"), PRESET = idx("preset"), NEXT = idx("preset_next"), PNAME = idx("patch_name"),
              REVT = idx("nvram_patchCommon_reverbtype"), CUT = idx("macro_cutoff"), ENVV = idx("envv_p_h_01"), BSLOT2 = idx("bank_slot_2"),
              BROWSE = idx("browse_bank_index");

    std::printf("== identity\n");
    AEffect* a = open("A");
    char name[64] = {0};
    a->dispatcher(a, effGetEffectName, 0, 0, name, 0);
    CHECK(a->uniqueID == (VstInt32)0x4a563838, "uid JV88 (%08x)", (unsigned)a->uniqueID);
    CHECK(!std::strcmp(name, JV_EXPECT_NAME), "name \"%s\"", name);
    CHECK(a->numParams == 472, "472 params (%d)", a->numParams);
    CHECK(a->dispatcher(a, effGetVendorVersion, 0, 0, nullptr, 0) == 2000, "version 2000");
    {
        int bad = 0;
        FILE* f = std::fopen("params.lock", "r");
        char line[128]; int i = 0;
        while (f && std::fgets(line, sizeof line, f)) { line[std::strcspn(line, "\r\n")] = 0; if (line[0] && std::strcmp(line, g_pspecs[i++].key)) bad++; }
        if (f) std::fclose(f);
        CHECK(f && bad == 0 && i == 470, "order = params.lock (%d keys, %d differ)", i, bad);
    }
    CHECK(waitReady(a), "ROMs loaded, patch list built (%s)", eng(a, "loading_status").c_str());

    std::printf("== sound\n");
    run(a, 200, {{0x90, 60, 100}});
    const double on = g_rms;
    run(a, 400, {{0x80, 60, 0}});
    const double off = g_rms;
    CHECK(on > 1e-3, "note on is audible (rms %.4f)", on);
    CHECK(off < on, "note off decays (rms %.4f)", off);

    std::printf("== value params\n");
    a->setParameter(a, P_LVL, norm(P_LVL, 90));
    settle(a);
    CHECK(engi(a, "nvram_patchCommon_patchlevel") == 90, "PATCH LVL 90 -> engine %d", engi(a, "nvram_patchCommon_patchlevel"));
    CHECK(disp(a, P_LVL) == "90", "PATCH LVL shows \"%s\"", disp(a, P_LVL).c_str());
    a->setParameter(a, REVT, 1.0f);
    settle(a);
    CHECK(engi(a, "nvram_patchCommon_reverbtype") == 7 && disp(a, REVT) == "PAN-DLY", "REVERB TYPE last option -> engine %d, \"%s\"",
          engi(a, "nvram_patchCommon_reverbtype"), disp(a, REVT).c_str());
    {   // a Q-Link nudge smaller than one step still moves one step (settle)
        const float cur = plainOf(a, P_LVL);
        a->setParameter(a, P_LVL, norm(P_LVL, cur) + 0.3f / 127.f);
        settle(a);
        CHECK(engi(a, "nvram_patchCommon_patchlevel") == (int)cur + 1 && std::lround(plainOf(a, P_LVL)) == (int)cur + 1,
              "a sub-step nudge up moves one step (%d -> engine %d, host %.0f)", (int)cur, engi(a, "nvram_patchCommon_patchlevel"), plainOf(a, P_LVL));
    }

    std::printf("== patch step, readback, text\n");
    const int p0 = engi(a, "preset");
    const std::string n0 = disp(a, PNAME);
    const float c0 = a->getParameter(a, PNAME);
    for (int i = 0; i < kNumParams; i++) g_automate[i] = 0;
    const int ud0 = g_updateDisplay;
    a->setParameter(a, NEXT, 1.0f);
    settle(a, 200);
    jv_dbg_tick(a);
    CHECK(engi(a, "preset") == p0 + 1, "PATCH + : engine preset %d -> %d", p0, engi(a, "preset"));
    CHECK(std::lround(plainOf(a, PRESET)) == p0 + 1, "host PATCH follows (%.0f)", plainOf(a, PRESET));
    CHECK(a->getParameter(a, NEXT) == 0.f, "PATCH + dropped back to 0");
    CHECK(disp(a, PNAME) != n0 && a->getParameter(a, PNAME) != c0, "patch name \"%s\" -> \"%s\", its counter moved", n0.c_str(), disp(a, PNAME).c_str());
    int told = 0;
    for (int i = 0; i < kNumParams; i++) told += g_automate[i] > 0;
    CHECK(told > 20 && g_updateDisplay > ud0, "the host heard about the new patch (%d params, %d display updates)", told, g_updateDisplay - ud0);
    {
        int bad = 0;
        for (int i = 0; i < kNumParams; i++)
        {
            const PSpec& s = g_pspecs[i];
            if (!(s.flags & kPolled) || (s.flags & kReadOnly) || i == 0) continue;
            const int ev = std::min(std::max(engi(a, s.key), (int)s.min), (int)s.max);   // clamped to the range, as 1.x did
            if (std::lround(plainOf(a, i)) != ev) { if (bad < 5) std::printf("    %s host %.0f engine %d\n", s.key, plainOf(a, i), engi(a, s.key)); bad++; }
        }
        CHECK(bad == 0, "every value param matches the engine after the load (%d differ)", bad);
    }

    std::printf("== parameter 0 (OCTAVE)\n");
    const int oct0 = engi(a, "octave_transpose");
    a->setParameter(a, 0, 1.0f); a->setParameter(a, 0, norm(0, (float)oct0));   // the host's prepare nudge
    settle(a);
    CHECK(engi(a, "octave_transpose") == oct0, "a nudge to the end and back changes nothing (%d)", engi(a, "octave_transpose"));
    a->setParameter(a, 0, norm(0, 2));
    run(a, 30);
    jv_dbg_tick(a);
    CHECK(engi(a, "octave_transpose") == 2, "a held change applies (%d)", engi(a, "octave_transpose"));

    std::printf("== read-only, tiles, MIDI control\n");
    const float ev0 = a->getParameter(a, ENVV);
    a->setParameter(a, ENVV, ev0 < 0.5f ? 1.f : 0.f);
    settle(a);
    CHECK(std::fabs(a->getParameter(a, ENVV) - ev0) < 1e-4f, "an envelope column ignores a host write");
    a->setParameter(a, BSLOT2, 1.0f);
    settle(a);
    CHECK(engi(a, "browse_bank_index") == 1 && a->getParameter(a, BSLOT2) == 1.f && std::lround(plainOf(a, BROWSE)) == 1,
          "BANK 2 tile: browses bank 2 and stays lit (%d)", engi(a, "browse_bank_index"));
    a->setParameter(a, BSLOT2, 0.0f);   // the host toggles a lit tile off: it stays lit
    settle(a);
    CHECK(a->getParameter(a, BSLOT2) == 1.f && !disp(a, BSLOT2).empty(), "a lit tile stays lit, shows \"%s\"", disp(a, BSLOT2).c_str());
    run(a, 2, {{0xB0, 20, 64}});   // CC 20 -> the first mapped control
    settle(a);
    CHECK(g_ccMap[0] == CUT && engi(a, "macro_cutoff") == 64 && std::lround(plainOf(a, CUT)) == 64, "CC 20 64 -> CUTOFF %d", engi(a, "macro_cutoff"));
    run(a, 2, {{0xB0, 99, 0}, {0xB0, 98, (uint8_t)P_LVL}, {0xB0, 6, 100}});
    settle(a);
    CHECK(engi(a, "nvram_patchCommon_patchlevel") == 100, "NRPN %d = 100 -> PATCH LVL %d", P_LVL, engi(a, "nvram_patchCommon_patchlevel"));

    std::printf("== state round trip\n");
    a->setParameter(a, PRESET, norm(PRESET, 12));
    settle(a, 200);
    a->setParameter(a, P_LVL, norm(P_LVL, 77));
    settle(a);
    const std::string patchA = eng(a, "patch_name");
    const std::vector<uint8_t> ca = chunk(a);
    CHECK(ca.size() > 1000 && !std::memcmp(ca.data(), "MPCP", 4), "A saves an SDK chunk (%zu bytes)", ca.size());
    AEffect* b = open("B");
    CHECK(waitReady(b), "B ready");
    b->setParameter(b, P_LVL, norm(P_LVL, 5));
    settle(b);
    CHECK(b->dispatcher(b, effSetChunk, 0, (VstIntPtr)ca.size(), (void*)ca.data(), 0) == 1, "B loads A's chunk");
    settle(b, 200);
    jv_dbg_tick(b);
    CHECK(engi(b, "preset") == 12 && engi(b, "nvram_patchCommon_patchlevel") == 77, "B: patch %d, PATCH LVL %d (the edit survives the load)",
          engi(b, "preset"), engi(b, "nvram_patchCommon_patchlevel"));
    CHECK(eng(b, "patch_name") == patchA && std::lround(plainOf(b, P_LVL)) == 77, "B: \"%s\", host PATCH LVL %.0f", eng(b, "patch_name").c_str(), plainOf(b, P_LVL));
    const std::vector<uint8_t> cb = chunk(b);
    CHECK(cb.size() > 1000, "B re-saves (%zu bytes)", cb.size());

    std::printf("== a 1.0.9 project\n");
    std::vector<uint8_t> legacy;
    if (FILE* f = std::fopen(legacyPath, "rb")) { int c; while ((c = std::fgetc(f)) != EOF) legacy.push_back((uint8_t)c); std::fclose(f); }
    CHECK(legacy.size() > 1000 && legacy[0] == '{', "read %s (%zu bytes)", legacyPath, legacy.size());
    AEffect* c = open("C");   // as the MPC does: the project's chunk arrives straight after the plugin opens, before the ROMs load
    CHECK(c->dispatcher(c, effSetChunk, 0, (VstIntPtr)legacy.size(), legacy.data(), 0) == 1, "C takes the 1.0.9 chunk at once");
    const std::vector<uint8_t> early = chunk(c);
    const std::string earlyS(early.begin(), early.end());
    CHECK(earlyS.find("\"preset\":37") != std::string::npos, "a save before the ROMs load keeps the project's state");
    CHECK(waitReady(c), "C ready");
    settle(c, 200);
    jv_dbg_tick(c);
    CHECK(engi(c, "preset") == 37 && disp(c, PNAME) == "Velo Harmnix", "C: patch %d \"%s\"", engi(c, "preset"), disp(c, PNAME).c_str());
    CHECK(engi(c, "nvram_patchCommon_patchlevel") == 90 && std::lround(plainOf(c, P_LVL)) == 90, "C: PATCH LVL %d (the 1.x edit)",
          engi(c, "nvram_patchCommon_patchlevel"));
    CHECK(engi(c, "macro_cutoff") == 100, "C: CUTOFF macro %d", engi(c, "macro_cutoff"));
    run(c, 200, {{0x90, 64, 100}});
    CHECK(g_rms > 1e-3, "C plays (rms %.4f)", g_rms);
    run(c, 50, {{0x80, 64, 0}});

    std::printf("== bad chunks\n");
    const char junk[] = "not a chunk";
    CHECK(c->dispatcher(c, effSetChunk, 0, sizeof junk, (void*)junk, 0) == 0, "junk is refused");
    const uint8_t cut[] = {'M', 'P', 'C', 'P', 2, 0, 0, 0, 200, 0, 0, 0, 5};
    CHECK(c->dispatcher(c, effSetChunk, 0, sizeof cut, (void*)cut, 0) == 0, "a truncated SDK chunk is refused");
    settle(c);
    CHECK(engi(c, "preset") == 37, "C still on patch 37");

    for (AEffect* e : {a, b, c}) { e->dispatcher(e, effMainsChanged, 0, 0, nullptr, 0); e->dispatcher(e, effClose, 0, 0, nullptr, 0); }
    if (g_fail) { std::printf("FAILED: %d checks\n", g_fail); return 1; }
    std::printf("OK\n");
    return 0;
}
