// JV-880 for MPC / Force: the MPC Plugin SDK front end (framework/mpc_plugin.h) around the unchanged JV-880 engine
// (src/dsp/jv880_plugin.cpp, a Schwung plugin_api_v2 module: nukeykt/giulioz core, patch browser, NVRAM parameters, state).
//
// Signal flow: host MIDI -> CC 20-35 / NRPN parameter control (as 1.x) or the engine -> the engine's own emulator thread fills a
// ring at 44.1 kHz -> render_block(128 frames, int16) -> a 128-frame FIFO here -> the host's block (any size).
//
// Parameters: the 1.0.9 build's 472 in the same order (params.json -> tools/sdk/gen_sdk_params.py -> params_gen.h).
//   * value params (kPolled): a host change goes to the engine as its own set_param string. The engine changes most of them by
//     itself (a patch load rewrites every NVRAM value, macros move, bank steps), so a worker thread reads them back and tells the host.
//     Whole-number and option params settle toward the direction of a Q-Link / wheel move, so a small turn always moves one step
//     (the 1.x wrapper's settle(); PATCH also counts any move up to 10 % of its range as one step).
//   * momentary verbs (kMomentary): 0 -> 1 fires the verb once (the engine fires on any value, so only the rising edge is sent), then
//     the param drops back to 0. PATCH -/+ (kStep) nudge PATCH. List tiles (kTile) fire on a tap and show the engine's "<key>_on".
//   * text readouts (kText): the value text is the engine's text; the value is a counter bumped when the text changes, because the
//     host only re-reads a param's text when its value moves.
//   * front-end functions (kLocal, no engine key): RANDOM loads a random patch from every bank. Favourites live in the MPC's own
//     PRESET list (the VST programs): +FAV saves the current patch with its edits (the engine's state: bank, patch, edited bytes) in
//     the first free slot, -FAV deletes the favourite that is picked. Program 0 is "Current patch" (picking it does nothing). The
//     slots are kept in <plugin folder>/jv880-favourites.dat, shared by every project.
//   * ui_open (kUi): which drawn pick-list the skin shows; never reaches the engine.
// Parameter 0 is OCTAVE. The host nudges parameter 0 to its far end and back on every prepare: a change applies only after it has
// held for ~40 ms, and a pair that ends where it started does nothing.
// State: the engine's own "state" JSON (mode, patch, the edited patch bytes) is the truth; it travels as the SDK chunk's extra state.
// While the SDK chunk restores parameter values nothing is written to the engine (a stored PATCH would reload the patch over its edits).
// A project saved by the 1.x wrapper build stored only that JSON as its chunk: it is still read (effSetChunk is wrapped below).

#include "mpc_plugin.h"
#include "mpc_resources.h"

#include "dsp/plugin_api_v1.h"
#include "params_gen.h"

#include <pthread.h>
#include <fstream>
#include <mutex>
#include <random>
#include <sys/stat.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

extern "C" plugin_api_v2_t* move_plugin_init_v2(const host_api_v1_t* host);

#ifndef JV_NAME
#define JV_NAME "JV-880"
#endif
#ifndef JV_UID
#define JV_UID 'J', 'V', '8', '8'
#endif
#define JV_FOURCC(...) MPC_FOURCC(__VA_ARGS__)   // expands JV_UID before MPC_FOURCC counts its arguments
#ifndef JV_VERSION
#define JV_VERSION 2000
#endif

namespace {

const int kBlock = 128;                 // the engine's block (Schwung contract)
const int kStateMax = 16384;            // the engine bounds its state to the Schwung host's 16 KB
const int kMidiSourceExternal = 2;

mpc::PluginInfo makeInfo()
{
    mpc::PluginInfo i;
    i.name = JV_NAME;
    i.vendor = "sd88me";
    i.uniqueId = JV_FOURCC(JV_UID);
    i.version = JV_VERSION;
    i.isInstrument = true;
    i.numInputs = 0;
    i.numOutputs = 2;
    return i;
}

long long nowMs()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

bool isFile(const std::string& p)
{
    struct stat st;
    return ::stat(p.c_str(), &st) == 0 && S_ISREG(st.st_mode);
}

// Where the ROMs are: <plugin folder>/jv880-roms/roms/ (1.x and the installer's ROM step), else Content/jv880-roms/roms/.
std::string dataDir()
{
    const std::string f = mpc::detail::computePluginFolder();   // not pluginFolder(): its static string crashes at dlclose
    const std::string a = f + "/jv880-roms", b = f + "/Content/jv880-roms";
    if (!isFile(a + "/roms/jv880_rom1.bin") && isFile(b + "/roms/jv880_rom1.bin")) return b;
    return a;
}

uint32_t fnv(const char* s)
{
    uint32_t h = 2166136261u;
    for (; *s; ++s) h = (h ^ (unsigned char)*s) * 16777619u;
    return h;
}

thread_local int t_pushing = -1;   // the parameter the worker is telling the host about right now (its echo is ignored)
thread_local bool t_absolute = false;   // the value being set is a value to go to (MIDI CC / NRPN), not a control being moved

} // namespace

class JV880Plugin : public mpc::Plugin
{
public:
    JV880Plugin() : mpc::Plugin(makeInfo())
    {
        for (int i = 0; i < kNumParams; ++i)
        {
            const PSpec& s = g_pspecs[i];
            mpc::Param p = (s.flags & kChoice)
                ? mpc::choiceParam(s.key, s.name, std::vector<std::string>(s.choices, s.choices + s.nchoices), (int)s.def)
                : mpc::intParam(s.key, s.name, (int)s.min, (int)s.max, (int)s.def);
            p.automatable = !(s.flags & kNoAuto);
            addParam(p);
        }
        const size_t n = (size_t)kNumParams;
        held_ = new std::atomic<bool>[n];
        release_ = new std::atomic<bool>[n];
        hostMoved_ = new std::atomic<bool>[n];
        for (size_t i = 0; i < n; ++i) { held_[i].store(false); release_[i].store(false); hostMoved_[i].store(false); }
        hostAt_ = new std::atomic<long long>[n];
        for (size_t i = 0; i < n; ++i) hostAt_[i].store(0);
        told_ = new std::atomic<float>[n];
        for (size_t i = 0; i < n; ++i) told_[i].store(-1.0e9f);
        lastPos_ = new std::atomic<float>[n];
        ahead_ = new std::atomic<bool>[n];
        stale_ = new std::atomic<float>[n];
        stepMag_ = new std::atomic<float>[n];
        for (size_t i = 0; i < n; ++i) { lastPos_[i].store(-1.0f); ahead_[i].store(false); stale_[i].store(-1.0f); stepMag_[i].store(-1.0f); }
        textHash_.assign(n, 0u);
        for (int i = 0; i < kNumParams; ++i)
        {
            if (!std::strcmp(g_pspecs[i].key, "preset")) presetIndex_ = i;
            if (!std::strcmp(g_pspecs[i].key, "browse_bank_index")) tileDue1_ = i;
            if (!std::strcmp(g_pspecs[i].key, "patch_page_index")) tileDue2_ = i;
        }

        pthread_mutexattr_t ma;   // recursive + priority-inheriting, as the 1.x wrapper: audio waiting on a short worker call lifts it
        pthread_mutexattr_init(&ma);
        pthread_mutexattr_settype(&ma, PTHREAD_MUTEX_RECURSIVE);
        pthread_mutexattr_setprotocol(&ma, PTHREAD_PRIO_INHERIT);
        pthread_mutex_init(&lock_, &ma);
        pthread_mutexattr_destroy(&ma);

        api_ = move_plugin_init_v2(nullptr);   // the engine ignores the host struct
        if (api_) inst_ = api_->create_instance(dataDir().c_str(), nullptr);   // fast: the ROM load runs on the engine's own thread
        if (std::strcmp(g_pspecs[kRandom].key, "patch_random") || std::strcmp(g_pspecs[kFavText].key, "fav_text")) std::abort();
        addProgram("Current patch", {});
        for (int i = 0; i < kFavSlots; ++i) addProgram("--", {});
        loadFavs();
        worker_ = std::thread(&JV880Plugin::workerMain, this);
    }

    ~JV880Plugin() override
    {
        quit_.store(true);
        if (worker_.joinable()) worker_.join();
        if (inst_) api_->destroy_instance(inst_);
        pthread_mutex_destroy(&lock_);
        delete[] held_;
        delete[] release_;
        delete[] hostMoved_;
        delete[] told_;
        delete[] hostAt_;
        delete[] lastPos_;
        delete[] ahead_;
        delete[] stale_;
        delete[] stepMag_;
    }

    void prepare(double, int maxBlockSize) override { setHostBlock(maxBlockSize); }

    // The engine keeps one host block (plus a margin) of audio ready: process() takes a whole block's worth of 128-frame
    // engine blocks back to back.
    void setHostBlock(int frames)
    {
        if (!inst_) return;
        Lock l(this);   // prepare() and process() can both come here: compare, store and send as one
        if (frames <= hostBlock_) return;
        hostBlock_ = frames;
        char b[16];
        std::snprintf(b, sizeof b, "%d", frames);
        api_->set_param(inst_, "host_block", b);
    }

    void reset() override
    {
        store(kUiParam, 0.0f);
        notifyUi_.store(true);
    }

    // ---- audio ----------------------------------------------------------------------------------------------------------------
    void process(mpc::ProcessContext& ctx) override
    {
        if (!inst_) return;
        if (ctx.numFrames > hostBlock_) setHostBlock(ctx.numFrames);   // a larger block than prepare() was told (rare, once)
        for (int k = 0; k < ctx.numMidiEvents; ++k)
        {
            const mpc::MidiEvent& e = ctx.midi[k];
            if (midiControl(e)) continue;
            if (e.size < 1) continue;
            uint8_t m[3] = {e.data[0], e.data[1], e.data[2]};
            Lock l(this);
            api_->on_midi(inst_, m, e.size > 3 ? 3 : e.size, kMidiSourceExternal);
        }
        float* L = ctx.outputs[0];
        float* R = ctx.numOutputs > 1 ? ctx.outputs[1] : nullptr;
        for (int i = 0; i < ctx.numFrames; ++i)
        {
            if (pos_ >= kBlock)
            {
                Lock l(this);
                api_->render_block(inst_, block_, kBlock);
                pos_ = 0;
            }
            L[i] = block_[pos_ * 2] * (1.0f / 32768.0f);
            if (R) R[i] = block_[pos_ * 2 + 1] * (1.0f / 32768.0f);
            ++pos_;
        }
    }

    // ---- parameters -----------------------------------------------------------------------------------------------------------
    void parameterChanged(int index, float plain) override
    {
        if (index < 0 || index >= kNumParams || !inst_) return;
        if (t_pushing == index) return;          // the host echoing what the worker just told it
        const PSpec& s = g_pspecs[index];
        if (s.flags & kAnchor) { hostMoved_[index].store(true); return; }   // an envelope's fixed start level: put back
        if (s.flags & kUi) return;
        if (s.flags & kLocal) { localChanged(index, s, plain); return; }
        hostAt_[index].store(nowMs());
        if (loading_.load()) return;             // an SDK chunk is restoring values: the engine state follows as extra state
        if ((s.flags & kChoice) && get(kUiParam) > 0.5f)   // a pick from the open drawn list closes it
        {
            store(kUiParam, 0.0f);
            notifyUi_.store(true);
        }
        if (s.flags & kReadOnly) { hostMoved_[index].store(true); return; }   // the worker puts the engine's value back
        if ((s.flags & kText) && !(s.flags & kTile)) return;   // a readout's counter: nothing to send
        if (s.flags & kMomentary)
        {
            if (plain < 0.5f) { held_[index].store(false); if (s.flags & kTile) hostMoved_[index].store(true); return; }
            if (held_[index].exchange(true))
            {
                if (s.flags & kTile) hostMoved_[index].store(true);   // not fired: the worker puts the tile's real state back
                return;
            }
            if (s.flags & kStep) stepTarget(s);
            else engineSet(s.key, "1");
            if (s.flags & kTile) hostMoved_[index].store(true);   // the tile shows "<key>_on", read back by the worker
            else release_[index].store(true);
            tilesDue_.store(true);   // a tile, a page arrow or a bank step: every tile's lit state may have changed
            return;
        }
        // whole numbers and options: settle toward the move (see settle()), then send
        const float span = s.max - s.min;
        float v = plain;
        bool pinned = false;
        int relative = 0;   // a nudged param moved by one step: -1 / +1 (0: an absolute value)
        if (span > 0)
        {
            const float pos = getNormalised(index) * span;
            float cur = told_[index] > -1.0e8f ? told_[index] - s.min : pos;
            if (s.nudgePct > 0)   // a stepped value (PATCH, BANK): step from where the engine is now, which is not always
            {                     // where it was last sent (a PATCH step on BANKS starts in the bank being browsed)
                char eb[32];
                if (engineGet(s.key, eb, sizeof eb)) cur = std::min(std::max((float)std::atof(eb), s.min), s.max) - s.min;
            }
            const float tick = s.nudgePct > 0 ? std::max(0.5f, span * s.nudgePct / 100.0f) : 0.5f;
            float steps;
            const float last = lastPos_[index].load();
            const bool nudged = s.nudgePct > 0 && !t_absolute;   // a MIDI set (CC / NRPN) is a value, never a nudge
            // A nudged param (PATCH, BANK) moves one step a tick. The worker does not send the engine's value back while the
            // host keeps moving the param (see hostAt_), so during a turn the host's own value runs ahead by its own step size
            // on every tick. ahead_ says that this has happened and the host has not been given the engine's value since
            // (pushValue clears it): the host's value is then no longer a position, and only the way it moves counts. Judging
            // it by distance made a fast turn jump to wherever the host's value had got to (another bank) once it left the
            // "one step" window; judging "a turn" by time made two quick sets look like one.
            bool turning = nudged && ahead_[index].load() && last >= 0;
            float base = last;   // what the host's value is compared with for the direction of a turn
            // After the worker has given the host the engine's value, the host's next move starts from that value, or, if
            // the control keeps a running value of its own (a Q-Link seems to), from where its own value was (stale_). The
            // move is a small one from one of the two: whichever is nearer is the one the control is moving from. Without
            // this a control that kept its own value looked, after any pause in a long turn, like a set to a far-away
            // number: the bank jump again.
            // "Nearer" is measured against the size of the control's last tick when that is known (a move of 37 from the
            // engine's value fits a 37-a-tick control better than a move of 35 from its old value).
            const float stale = stale_[index].load();
            if (nudged && !turning && stale >= 0 && std::fabs(pos - stale) < std::max(1.5f, span / 50.0f))   // within a tick's reach
            {
                const float dH = std::fabs(pos - stale), dV = std::fabs(pos - cur), mag = stepMag_[index].load();
                if (mag > 0 ? std::fabs(dH - mag) < std::fabs(dV - mag) : dH < dV)
                {
                    turning = true;
                    base = stale;
                }
            }
            // The host's value also reaches an end of the range long before the patch does (PATCH spans 0..8191 and the
            // first banks sit at the bottom): it then cannot move further and the turn would stop. Within a turn, or when the
            // end is no further from the engine's value than one tick of a control can reach (2 % of the range), an end is
            // one more step that way, and the worker sends the engine's value back at once (no hold) so the host's value
            // has room again. A set to an end from further away is that value (the first patch, the last wave).
            const bool atLo = pos <= 0.001f, atHi = pos >= span - 0.001f;
            pinned = nudged && ((atLo && cur > 0.5f) || (atHi && cur < span - 0.5f)) &&
                                (turning || std::fabs(pos - cur) < std::max(1.5f, span / 50.0f));
            float seen = pos;
            char how = 'a';   // for the trace: a = absolute, p = pinned, t = turning, n = nudge
            if (pinned)
            {
                relative = atLo ? -1 : 1;
                stale_[index].store(pos);
                seen = -1.0f;   // the host's value is about to be replaced: the next move is judged against the engine's
                how = 'p';
            }
            else if (turning)
            {
                relative = pos > base ? 1 : pos < base ? -1 : 0;
                if (!atLo && !atHi && std::fabs(pos - base) > 0.0005f) stepMag_[index].store(std::fabs(pos - base));
                how = base == last ? 't' : 's';
            }
            else if (nudged && std::fabs(pos - std::round(pos)) > 0.001f && std::fabs(pos - cur) < tick)
            {
                relative = pos > cur ? 1 : -1;
                if (!atLo && !atHi) stepMag_[index].store(std::fabs(pos - cur));
                stale_[index].store(-1.0f);   // the host moved on from the engine's value: it does take it over
                how = 'n';
            }
            if (pinned || turning || relative != 0)
                steps = std::round(cur) + (float)relative;
            else
                steps = settle(pos, cur, last);
            lastPos_[index].store(seen);
            if (s.nudgePct > 0) trace(t_absolute ? 'M' : 'H', index, pos, cur, last, stale, how, relative, std::min(std::max(steps, 0.0f), span));
            steps = std::min(std::max(steps, 0.0f), span);
            v = s.min + steps;
            // Where it landed reaches the host from the worker, ~10 ms later (as 1.x reported the engine's value): the host's own
            // value is left as it set it until then, so a set reads back unchanged (host_sim's sweep checks that).
            if (std::fabs(getNormalised(index) * span - steps) > 0.001f)
            {
                hostMoved_[index].store(true);
                if (nudged) ahead_[index].store(true);
            }
            else if (s.nudgePct > 0)
                ahead_[index].store(false);   // the host's value is the value sent: in step again without a read-back
        }
        if (index == 0)   // OCTAVE: debounced (see the header comment)
        {
            pend0Value_.store(v);
            pend0At_.store(nowMs());
            return;
        }
        char buf[24];
        told_[index] = v;
        if (index == tileDue1_ || index == tileDue2_) tilesDue_.store(true);   // the lists now show another bank / page
        if (relative != 0 && index == presetIndex_)
        {
            // PATCH by one step is sent as a step, not as a number: on BANKS the engine starts it in the bank being browsed,
            // and a patch number that happens to be next to the current one (RANDOM, a recalled value) must not do that.
            std::snprintf(buf, sizeof buf, "%d", relative);
            engineSet("preset_step", buf);
        }
        else
        {
            std::snprintf(buf, sizeof buf, "%d", (int)std::lround(v));
            engineSet(s.key, buf);
        }
        // A pinned end: the worker sends the engine's value back at once (no hold). Only now, after told_ and the engine have
        // the new value: cleared earlier, the worker could read back the old patch in between and leave the host on it.
        if (pinned) hostAt_[index].store(0);
    }

    bool formatValue(int index, float plain, std::string& out) override
    {
        (void)plain;
        if (index < 0 || index >= kNumParams) return false;
        const PSpec& s = g_pspecs[index];
        if ((s.flags & kText) && (s.flags & kLocal)) { out = localText(index); return true; }
        if (s.flags & kText)   // the engine's text (a tile's name, a bank / patch name, the page text)
        {
            char buf[128];
            out = engineGet(s.key, buf, sizeof buf) ? buf : "";
            return true;
        }
        if (s.flags & kMomentary) { out = ""; return true; }
        if (s.flags & kUi) { out = ""; return true; }
        return false;
    }

    // ---- state ----------------------------------------------------------------------------------------------------------------
    void saveExtraState(std::vector<uint8_t>& out) override
    {
        std::string s = engineState();
        out.assign(s.begin(), s.end());
    }

    void loadExtraState(const uint8_t* data, size_t size) override
    {
        if (!data || !size) return;
        ignoreProgUntil_.store(nowMs() + 2000);   // the host re-picks the saved program after a project load: the project's patch wins
        applyState(std::string(reinterpret_cast<const char*>(data), strnlen(reinterpret_cast<const char*>(data), size)));
    }

    // A project saved by the 1.x wrapper build: its chunk is the engine's state JSON, NUL-terminated. Called from the wrapped effSetChunk.
    bool loadLegacy(const char* data, size_t size)
    {
        if (!data || !size) return false;
        std::string s(data, strnlen(data, size));
        size_t b = s.find_first_not_of(" \t\r\n");
        if (b == std::string::npos || s[b] != '{') return false;
        ignoreProgUntil_.store(nowMs() + 2000);
        applyState(s);
        return true;
    }

    std::atomic<bool> loading_{false};   // set around an SDK chunk load (wrapped effSetChunk)
    void requestResync() { resync_.store(true); }

private:
    struct Lock
    {
        explicit Lock(JV880Plugin* p) : p_(p) { pthread_mutex_lock(&p_->lock_); }
        ~Lock() { pthread_mutex_unlock(&p_->lock_); }
        JV880Plugin* p_;
    };

    void engineSet(const char* key, const char* val)
    {
        Lock l(this);
        api_->set_param(inst_, key, val);
    }

    bool engineGet(const char* key, char* buf, int n)
    {
        int r;
        { Lock l(this); r = api_->get_param(inst_, key, buf, n); }
        if (r <= 0) { buf[0] = 0; return false; }
        buf[r < n ? r : n - 1] = 0;
        return true;
    }

    // The engine's state, or (while it is still loading, or has no ROMs) the last state it was given, so a save never drops it.
    std::string engineState()
    {
        std::string s;
        if (inst_)
        {
            std::vector<char> buf((size_t)kStateMax + 1);
            if (engineGet("state", buf.data(), kStateMax)) s = buf.data();
        }
        if (s.empty()) { Lock l(this); s = lastState_; }
        return s;
    }

    void applyState(const std::string& s)
    {
        { Lock l(this); lastState_ = s; }
        if (inst_) engineSet("state", s.c_str());   // queued by the engine until its ROMs have loaded
        resync_.store(true);
    }

    // Set a parameter's value without calling parameterChanged (so it is not written back to the engine).
    void store(int i, float plain) { values_[(size_t)i]->store(param(i).toNormalised(plain), std::memory_order_relaxed); }

    // Where a whole-number / option param lands, in steps from its minimum (the 1.x wrapper's rule): a value on a step is a click,
    // a preset or automation; between steps it is a Q-Link / wheel / drag move, rounded toward the way it moves, so a turn smaller
    // than one step still moves one and a sweep does not flicker between two values.
    static float settle(float pos, float cur, float last)
    {
        if (std::fabs(pos - std::round(pos)) <= 0.001f) return std::round(pos);
        const float dir = (last >= 0 && std::fabs(pos - last) < 0.5f) ? pos - last : pos - cur;
        if (dir == 0) return std::round(cur);
        return dir > 0 ? std::ceil(pos - 0.001f) : std::floor(pos + 0.001f);
    }

    void stepTarget(const PSpec& s)   // PATCH -/+: nudge the target from the engine's current value
    {
        const PSpec& t = g_pspecs[s.stepTarget];
        char buf[32];
        if (s.stepTarget == presetIndex_)   // PATCH -/+: a step, which on BANKS starts in the bank being browsed
        {
            std::snprintf(buf, sizeof buf, "%d", (int)std::lround(s.stepDelta));
            engineSet("preset_step", buf);
        }
        else
        {
            if (!engineGet(t.key, buf, sizeof buf)) return;
            float v = (float)std::atof(buf) + s.stepDelta;
            v = std::min(std::max(v, t.min), t.max);
            std::snprintf(buf, sizeof buf, "%d", (int)std::lround(v));
            engineSet(t.key, buf);
        }
        release_[&s - g_pspecs].store(true);
        hostMoved_[s.stepTarget].store(true);
    }

    // CC 20-35 -> the first page's controls, NRPN n -> parameter n (1.x). Set as a touch would; the worker tells the host.
    bool midiControl(const mpc::MidiEvent& e)
    {
        if ((e.data[0] & 0xF0) != 0xB0 || e.size < 3) return false;
        const int cc = e.data[1] & 127, v = e.data[2] & 127;
        if (cc >= 20 && cc <= 35 && g_ccMap[cc - 20] >= 0) { ccSet(g_ccMap[cc - 20], v / 127.0f); return true; }
        if (!kHasNrpn) return false;
        if (cc == 99) { nrpn_ = (v << 7) | (nrpn_ >= 0 ? nrpn_ & 127 : 0); return true; }
        if (cc == 98) { nrpn_ = (nrpn_ >= 0 ? nrpn_ & ~127 : 0) | v; return true; }
        if (cc == 101 || cc == 100) { nrpn_ = -1; return false; }   // an RPN (bend range ...): the engine's
        if (nrpn_ >= 0 && nrpn_ < kNumParams && cc == 6) { nrpnMsb_ = v; ccSet(nrpn_, v / 127.0f); return true; }
        if (nrpn_ >= 0 && nrpn_ < kNumParams && cc == 38) { ccSet(nrpn_, (nrpnMsb_ * 128 + v) / 16383.0f); return true; }
        return false;
    }

    void ccSet(int i, float norm)
    {
        if (i < 0 || i >= kNumParams || (g_pspecs[i].flags & kUi)) return;
        const mpc::Param& p = param(i);
        const float span = p.max - p.min;
        if (span > 0) norm = std::round(norm * span) / span;   // onto a step: a direct set, not a nudge
        t_absolute = true;
        setNormalised(i, norm);
        t_absolute = false;
        hostMoved_[i].store(true);
    }

    // ---- worker: debounced OCTAVE, momentary releases, and everything the engine changes by itself ------------------------------
    void pushValue(int i, float plain)
    {
        // The host has the engine's value again: its next move is judged against that, or, if the control keeps a running
        // value of its own, against where that had got to (only kept when it had run ahead; see parameterChanged).
        const bool wasAhead = ahead_[i].exchange(false);
        const float was = lastPos_[i].exchange(-1.0f);
        if (was >= 0) stale_[i].store(wasAhead ? was : -1.0f);
        if (g_pspecs[i].nudgePct > 0) trace('P', i, was, plain - g_pspecs[i].min, -1.0f, stale_[i].load(), '-', 0, plain - g_pspecs[i].min);
        told_[i] = plain;
        store(i, plain);
        t_pushing = i;
        notifyHostParameterChanged(i);
        t_pushing = -1;
    }

    void workerMain()
    {
        while (!quit_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            tickOnce(false);
        }
    }

    // One worker pass. force = the offline test: apply a pending OCTAVE now and read back everything.
    void tickOnce(bool force)
    {
        if (!inst_) return;
        const long long now = nowMs();
        ++tick_;
        if (tick_ % 50 == 0) flushTrace();
        const long long p0 = pend0At_.load();
        if (p0 && (force || now - p0 >= 40))
        {
            pend0At_.store(0);
            const float v = pend0Value_.load();
            char buf[24];
            if (engineGet(g_pspecs[0].key, buf, sizeof buf) && std::lround(std::atof(buf)) != std::lround(v))
            {
                std::snprintf(buf, sizeof buf, "%d", (int)std::lround(v));
                engineSet(g_pspecs[0].key, buf);
            }
            told_[0] = -1.0e9f;   // read back below
        }
        for (int i = 0; i < kNumParams; ++i)
            if (release_[i].exchange(false)) { held_[i].store(false); pushValue(i, 0.0f); }
        {   // a favourite picked in the MPC's PRESET list (not the re-pick that follows a project load: the project's patch wins)
            const int prog = currentProgram();
            if (prog != lastProgram_)
            {
                lastProgram_ = prog;
                if (prog > 0 && now >= ignoreProgUntil_.load()) loadFav(prog - 1);
            }
        }
        if (favDirty_.exchange(false)) { saveFavs(); wantDisplay_ = true; }   // new names in the PRESET list and the status text
        if (notifyUi_.exchange(false)) { t_pushing = kUiParam; notifyHostParameterChanged(kUiParam); t_pushing = -1; }
        if (resync_.exchange(false))
        {
            for (int i = 0; i < kNumParams; ++i) told_[i].store(-1.0e9f);
            std::fill(textHash_.begin(), textHash_.end(), 0u);
            for (int i = 0; i < kNumParams; ++i) hostMoved_[i].store(true);
            lastRev_ = 0;
        }

        // the envelope-view columns follow "display_rev" (which also times the views out); read every 100 ms
        bool revChanged = false;
        if (force || tick_ % 10 == 0)
        {
            char rb[16];
            if (engineGet("display_rev", rb, sizeof rb))
            {
                const uint32_t r = fnv(rb) | 1u;
                revChanged = r != lastRev_;
                lastRev_ = r;
            }
        }

        // values: every pass for the ones the host just moved; all of them at once when the patch changed (a load rewrites every
        // NVRAM value; "patch_sig" = the engine's mode / patch / patch name, read every pass); otherwise kSweep per pass, round-robin
        // (each value about every 200 ms: macros and edits the engine makes by itself)
        char buf[128];
        bool full = force;
        {
            std::string sig;
            // "patch_serial": a patch on another card reaches the engine's memory after "preset" changed (the card loads first)
            for (const char* k : {"mode", "preset", "performance", "patch_name", "loading_complete", "patch_serial"})
                if (engineGet(k, buf, sizeof buf)) { sig += buf; sig += '|'; }
            const uint32_t h = fnv(sig.c_str()) | 1u;
            if (h != patchSig_) { patchSig_ = h; full = true; }
        }
        const int first = cursor_;
        cursor_ = (cursor_ + kSweep) % kNumParams;
        int changed = 0;
        // A tap, a page arrow or a browsed bank changes which tiles are lit without changing the patch: read every tile now,
        // not in its turn (about 260 ms), or a tile the host still shows lit swallows the next tap on it.
        const bool tiles = tilesDue_.exchange(false);
        for (int i = 0; i < kNumParams; ++i)
        {
            const PSpec& s = g_pspecs[i];
            const bool moved = hostMoved_[i].exchange(false);
            const bool due = full || (tiles && (s.flags & kTile)) || (i - first + kNumParams) % kNumParams < kSweep;
            if (s.flags & kTile)
            {
                if (!(moved || due)) continue;
                char k2[64];
                std::snprintf(k2, sizeof k2, "%s_on", s.key);
                const float on = engineGet(k2, buf, sizeof buf) && std::atoi(buf) ? 1.0f : 0.0f;
                if (moved || on != told_[i])
                {
                    // A tile the engine turned off (another patch or bank was picked) is no longer held. The host sends no 0
                    // for it, so it stayed "held": its next tap was not sent to the engine, yet the host lit it, beside the
                    // tile of the patch that really was loaded.
                    if (on < 0.5f) held_[i].store(false);
                    pushValue(i, on);
                    if (!moved) ++changed;
                }
                continue;
            }
            if (s.flags & kAnchor) { if (moved || told_[i] < -1.0e8f) pushValue(i, s.def); continue; }
            if (!(s.flags & kPolled)) continue;
            if (i == 0 && pend0At_.load()) continue;   // OCTAVE not applied yet
            if ((s.flags & kReadOnly) ? !(moved || revChanged || told_[i] < -1.0e8f) : !(moved || due)) continue;
            // while the host is still moving it (an envelope handle or a cell being dragged), don't send the engine's value back
            // under the finger: it would fight the drag. Read it back once the drag has rested for 300 ms.
            if (!force && now - hostAt_[i].load() < 300) { if (moved) hostMoved_[i].store(true); continue; }
            if (!engineGet(s.key, buf, sizeof buf)) continue;
            float v = (float)std::atof(buf);
            v = std::min(std::max(v, s.min), s.max);
            if (moved || v != told_[i]) { pushValue(i, v); if (!moved) ++changed; }
        }

        // text readouts: every 100 ms; a changed text bumps the counter (the host re-reads text when the value moves)
        bool textChanged = false;
        if (force || tick_ % 10 == 0)
            for (int i = 0; i < kNumParams; ++i)
            {
                const PSpec& s = g_pspecs[i];
                if (!(s.flags & kText)) continue;
                const uint32_t h = (s.flags & kLocal) ? fnv(localText(i).c_str()) | 1u
                                                      : engineGet(s.key, buf, sizeof buf) ? fnv(buf) | 1u : 1u;
                if (h == textHash_[(size_t)i]) continue;
                textHash_[(size_t)i] = h;
                textChanged = true;
                if (s.flags & kTile) continue;   // a tile's value is its lit state
                counter_ = (counter_ + 1) % 1024;
                pushValue(i, (float)counter_);
            }
        // Many values at once (a patch load) or new text: one display update, at most every 100 ms. Never periodically: it re-lists
        // programs and closes the PRESET menu.
        if (textChanged || changed > 8) wantDisplay_ = true;
        if (wantDisplay_ && (force || now - lastDisplay_ >= 100))
        {
            wantDisplay_ = false;
            lastDisplay_ = now;
            requestDisplayUpdate();
        }
    }

    // ---- random patch, favourites (kLocal) ---------------------------------------------------------------------------------------
    static constexpr int kRandom = 506, kFavSave = 507, kFavDelete = 508, kFavText = 509, kFavSlots = 64;
    struct Fav { bool used = false; std::string name, state; };

    static std::string favFile() { return mpc::detail::computePluginFolder() + "/jv880-favourites.dat"; }

    // "JVF1", slot count, then per slot: used (1 byte), name length + name, state length + state (u32 little endian lengths)
    void loadFavs()
    {
        std::lock_guard<std::mutex> g(favMu_);
        favs_.assign(kFavSlots, Fav());
        std::ifstream f(favFile(), std::ios::binary);
        char magic[4] = {};
        uint32_t n = 0;
        if (f.read(magic, 4) && !std::memcmp(magic, "JVF1", 4) && f.read(reinterpret_cast<char*>(&n), 4))
            for (uint32_t i = 0; i < n && i < (uint32_t)kFavSlots; ++i)
            {
                char used = 0;
                uint32_t ln = 0, ls = 0;
                if (!f.read(&used, 1) || !f.read(reinterpret_cast<char*>(&ln), 4) || ln > 256) break;
                std::string name(ln, '\0');
                if (ln && !f.read(&name[0], ln)) break;
                if (!f.read(reinterpret_cast<char*>(&ls), 4) || ls > (uint32_t)kStateMax) break;
                std::string st(ls, '\0');
                if (ls && !f.read(&st[0], ls)) break;
                favs_[i].used = used != 0 && ls > 0;
                favs_[i].name = name;
                favs_[i].state = st;
            }
        for (int i = 0; i < kFavSlots; ++i) nameProgram(i);
    }

    void saveFavs()   // worker thread: a snapshot under the lock, then the file (.tmp + rename)
    {
        std::vector<Fav> snap;
        { std::lock_guard<std::mutex> g(favMu_); snap = favs_; }
        const std::string tmp = favFile() + ".tmp";
        {
            std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
            if (!f) return;
            const uint32_t n = (uint32_t)snap.size();
            f.write("JVF1", 4);
            f.write(reinterpret_cast<const char*>(&n), 4);
            for (const Fav& v : snap)
            {
                const char used = v.used ? 1 : 0;
                const uint32_t ln = (uint32_t)v.name.size(), ls = (uint32_t)v.state.size();
                f.write(&used, 1);
                f.write(reinterpret_cast<const char*>(&ln), 4);
                f.write(v.name.data(), ln);
                f.write(reinterpret_cast<const char*>(&ls), 4);
                f.write(v.state.data(), ls);
            }
        }
        std::rename(tmp.c_str(), favFile().c_str());
    }

    void nameProgram(int i)   // favMu_ held
    {
        programs_[(size_t)i + 1].name = std::to_string(i + 1) + " " + (favs_[(size_t)i].used ? favs_[(size_t)i].name : std::string("--"));
    }

    std::string localText(int i)
    {
        if (i != kFavText) return "";
        int n = 0;
        { std::lock_guard<std::mutex> g(favMu_); for (const Fav& v : favs_) n += v.used ? 1 : 0; }
        return std::to_string(n) + " / " + std::to_string(kFavSlots) + " SAVED";
    }

    void loadFav(int slot)   // worker thread
    {
        std::string st;
        { std::lock_guard<std::mutex> g(favMu_); if (slot >= 0 && slot < kFavSlots && favs_[(size_t)slot].used) st = favs_[(size_t)slot].state; }
        if (st.empty()) return;
        applyState(st);
        requestResync();   // every value follows the loaded patch
    }

    void selectPatch(int index)
    {
        char b[24];
        std::snprintf(b, sizeof b, "%d", index);
        engineSet("preset", b);
        for (int i = 0; i < kNumParams; ++i)   // PATCH reads back on the next pass (the patch signature change sweeps the rest)
            if (!std::strcmp(g_pspecs[i].key, "preset")) { told_[i].store(-1.0e9f); hostMoved_[i].store(true); }
    }

    void localChanged(int index, const PSpec& s, float plain)
    {
        (void)s;
        if (plain < 0.5f) { held_[index].store(false); return; }
        if (held_[index].exchange(true)) return;
        release_[index].store(true);   // a momentary: back to 0 on the next worker pass
        char b[128];
        if (index == kRandom)
        {
            const int n = engineGet("total_patches", b, sizeof b) ? std::atoi(b) : 0;
            if (n > 1)
            {
                const int cur = engineGet("preset", b, sizeof b) ? std::atoi(b) : -1;
                int r;
                do r = (int)(rng_() % (uint32_t)n); while (r == cur);
                selectPatch(r);
            }
            return;
        }
        if (index == kFavSave)
        {
            Fav v;
            v.state = engineState();
            if (engineGet("patch_name", b, sizeof b)) v.name = b;
            while (!v.name.empty() && v.name.back() == ' ') v.name.pop_back();
            if (v.name.empty()) v.name = "Favourite";
            if (v.state.empty() || v.state[0] != '{') return;
            v.used = true;
            int slot = -1;
            {
                std::lock_guard<std::mutex> g(favMu_);
                for (int i = 0; i < kFavSlots && slot < 0; ++i) if (!favs_[(size_t)i].used) slot = i;
                if (slot >= 0) { favs_[(size_t)slot] = v; nameProgram(slot); }
            }
            if (slot >= 0) favDirty_.store(true);
            return;
        }
        if (index == kFavDelete)   // the favourite that is picked now
        {
            const int prog = currentProgram();
            if (prog < 1) return;
            bool had;
            {
                std::lock_guard<std::mutex> g(favMu_);
                had = favs_[(size_t)prog - 1].used;
                if (had) { favs_[(size_t)prog - 1] = Fav(); nameProgram(prog - 1); }
            }
            if (had) favDirty_.store(true);
        }
    }

public:
#ifdef JV_TEST
    void dbgTick() { tickOnce(true); }
    bool dbgReady()
    {
        char b[16];
        return engineGet("loading_complete", b, sizeof b) ? std::atoi(b) != 0 : engineState().size() > 0 && engineState()[0] == '{';
    }
    std::string dbgEngine(const char* key)
    {
        char b[256];
        return engineGet(key, b, sizeof b) ? std::string(b) : std::string();
    }
    void dbgEngineSet(const char* key, const char* v) { engineSet(key, v); }
    std::string dbgState() { return engineState(); }
#endif

private:
    plugin_api_v2_t* api_ = nullptr;
    void* inst_ = nullptr;
    pthread_mutex_t lock_;   // one engine call at a time (the engine assumes a single caller); held for microseconds
    std::thread worker_;
    std::atomic<bool> quit_{false};
    std::atomic<bool> resync_{true}, notifyUi_{false};
    std::atomic<long long> pend0At_{0};
    std::atomic<float> pend0Value_{0.0f};
    std::atomic<bool>* held_ = nullptr;
    std::atomic<bool>* release_ = nullptr;
    std::atomic<bool>* hostMoved_ = nullptr;   // read this one back and tell the host on the next pass
    std::atomic<long long>* hostAt_ = nullptr;   // when the host last moved it (ms), per parameter
    std::atomic<float>* told_ = nullptr;       // the value the host was last told (or sent), per parameter
    std::atomic<float>* lastPos_ = nullptr;    // the host's last position (-1: none), for settle() and the direction of a turn
    std::atomic<bool>* ahead_ = nullptr;       // a nudged param: the host's own value has run ahead of the engine's (see parameterChanged)
    std::atomic<float>* stale_ = nullptr;      // a nudged param: the host's own value when it was last given the engine's (-1: none)
    std::atomic<float>* stepMag_ = nullptr;    // a nudged param: how far the host's value moved on its last tick (-1: not known)
    std::atomic<bool> tilesDue_{false};        // read every tile's lit state on the next worker pass

    // JV_TRACE builds: every move of a stepped param (PATCH, BANK, wave number) and every value sent back to the host, written
    // by the worker to <plugin folder>/jv880-trace.txt. For finding out what a real host sends; not in release builds.
#ifdef JV_TRACE
    struct Tr { long long t; float pos, cur, last, stale, sent; short idx; signed char rel; char kind, how; };
    static const unsigned kTr = 8192;
    Tr tr_[kTr];
    std::atomic<unsigned> trN_{0};
    unsigned trDone_ = 0;
    void trace(char kind, int idx, float pos, float cur, float last, float stale, char how, int rel, float sent)
    {
        Tr& r = tr_[trN_.fetch_add(1) % kTr];
        r.t = nowMs(); r.pos = pos; r.cur = cur; r.last = last; r.stale = stale; r.sent = sent;
        r.idx = (short)idx; r.rel = (signed char)rel; r.kind = kind; r.how = how;
    }
    void flushTrace()   // worker thread
    {
        const unsigned n = trN_.load();
        if (n == trDone_) return;
        if (n - trDone_ > kTr) trDone_ = n - kTr;
        if (std::FILE* f = std::fopen((mpc::detail::computePluginFolder() + "/jv880-trace.txt").c_str(), "a"))
        {
            for (; trDone_ != n; ++trDone_)
            {
                const Tr& r = tr_[trDone_ % kTr];
                std::fprintf(f, "%lld %c %s host=%.3f engine=%.0f last=%.3f stale=%.3f %c rel=%d sent=%.0f\n", r.t, r.kind,
                             g_pspecs[r.idx].key, r.pos, r.cur, r.last, r.stale, r.how, (int)r.rel, r.sent);
            }
            std::fclose(f);
        }
        trDone_ = n;
    }
#else
    void trace(char, int, float, float, float, float, char, int, float) {}
    void flushTrace() {}
#endif
    int presetIndex_ = -1, tileDue1_ = -1, tileDue2_ = -1;   // PATCH; the params that change what the BANKS lists show
    std::vector<uint32_t> textHash_;
    std::mutex favMu_;
    std::vector<Fav> favs_;
    std::mt19937 rng_{std::random_device{}()};
    std::atomic<bool> favDirty_{false};
    std::atomic<long long> ignoreProgUntil_{0};
    int lastProgram_ = 0;   // worker thread
    std::string lastState_;
    int16_t block_[kBlock * 2] = {0};
    int pos_ = kBlock;
    int hostBlock_ = 0;   // the largest host block seen (frames), as told to the engine
    int nrpn_ = -1, nrpnMsb_ = 0;
    uint32_t lastRev_ = 0, patchSig_ = 0;
    int cursor_ = 0;
    static const int kSweep = 24;
    int counter_ = 0;
    long tick_ = 0;
    bool wantDisplay_ = false;
    long long lastDisplay_ = 0;
};

// The same entry as MPC_PLUGIN_ENTRY, plus a wrapped effSetChunk: an "MPCP" chunk loads with engine writes held back (the engine
// state in its extra part is the truth); a 1.x chunk (the engine's JSON) goes to the engine as before.
namespace {
VstIntPtr (*g_origDispatcher)(AEffect*, VstInt32, VstInt32, VstIntPtr, void*, float) = nullptr;

VstIntPtr jvDispatcher(AEffect* e, VstInt32 opcode, VstInt32 index, VstIntPtr value, void* ptr, float opt)
{
    if (opcode == effSetChunk && e->object && ptr && value > 0)
    {
        JV880Plugin* p = static_cast<JV880Plugin*>(e->object);
        if (value >= 4 && std::memcmp(ptr, "MPCP", 4) == 0)
        {
            p->loading_.store(true);
            const VstIntPtr r = g_origDispatcher(e, opcode, index, value, ptr, opt);
            p->loading_.store(false);
            p->requestResync();
            return r;
        }
        return p->loadLegacy(static_cast<const char*>(ptr), (size_t)value) ? 1 : 0;
    }
    return g_origDispatcher(e, opcode, index, value, ptr, opt);
}
} // namespace

#ifdef JV_TEST   // offline test hooks (tests/host_test.cpp); absent from the release build
extern "C" MPC_EXPORT void jv_dbg_tick(AEffect* e) { static_cast<JV880Plugin*>(e->object)->dbgTick(); }
extern "C" MPC_EXPORT int jv_dbg_ready(AEffect* e) { return static_cast<JV880Plugin*>(e->object)->dbgReady() ? 1 : 0; }
extern "C" MPC_EXPORT int jv_dbg_engine(AEffect* e, const char* key, char* out, int n)
{
    std::string s = static_cast<JV880Plugin*>(e->object)->dbgEngine(key);
    std::snprintf(out, (size_t)n, "%s", s.c_str());
    return (int)s.size();
}
extern "C" MPC_EXPORT int jv_dbg_state(AEffect* e, char* out, int n)   // the engine's whole state (jv_dbg_engine stops at 255 characters)
{
    std::string s = static_cast<JV880Plugin*>(e->object)->dbgState();
    std::snprintf(out, (size_t)n, "%s", s.c_str());
    return (int)s.size();
}
extern "C" MPC_EXPORT void jv_dbg_engine_set(AEffect* e, const char* key, const char* v) { static_cast<JV880Plugin*>(e->object)->dbgEngineSet(key, v); }
#endif

extern "C" MPC_EXPORT AEffect* VSTPluginMain(audioMasterCallback host)
{
    if (host != nullptr && host(nullptr, audioMasterVersion, 0, 0, nullptr, 0.0f) == 0) return nullptr;   // host is VST1 only
    AEffect* e = mpc::detail::createEffect(new JV880Plugin(), host);
    if (e && !g_origDispatcher) g_origDispatcher = e->dispatcher;
    if (e) e->dispatcher = jvDispatcher;
    return e;
}
