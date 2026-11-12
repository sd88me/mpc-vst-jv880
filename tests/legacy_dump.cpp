// tests/make_legacy_chunk.sh: drive the released 1.0.9 build (wrapper + engine, x86) like a host and save its effGetChunk.
#include <dlfcn.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>
#include <chrono>

struct AEffect;
typedef intptr_t (*cb)(AEffect*, int32_t, int32_t, intptr_t, void*, float);
struct AEffect {
    int32_t magic;
    intptr_t (*d)(AEffect*, int32_t, int32_t, intptr_t, void*, float);
    void* proc;
    void (*setP)(AEffect*, int32_t, float);
    float (*getP)(AEffect*, int32_t);
    int32_t np, npar, ni, no, flags;
    intptr_t r1, r2;
    int32_t a, b, c;
    float io;
    void *obj, *user;
    int32_t uid, ver;
    void (*pr)(AEffect*, float**, float**, int32_t);
};
static intptr_t host(AEffect*, int32_t op, int32_t, intptr_t, void*, float) { return op == 1 ? 2400 : 0; }

static void run(AEffect* e, int blocks)   // real time: the engine's emulator thread fills its ring at its own pace
{
    float L[128], R[128], *out[2] = {L, R};
    for (int i = 0; i < blocks; i++) { e->pr(e, nullptr, out, 128); std::this_thread::sleep_for(std::chrono::microseconds(2900)); }
}

int main(int argc, char** argv)
{
    if (argc < 3) return 2;
    void* h = dlopen(argv[1], RTLD_NOW);
    if (!h) { std::fprintf(stderr, "%s\n", dlerror()); return 1; }
    auto main_ = (AEffect* (*)(cb))dlsym(h, "VSTPluginMain");
    AEffect* e = main_(host);
    std::printf("1.0.9: uid=%x params=%d version=%d\n", e->uid, e->npar, e->ver);
    char disp[128];
    for (int t = 0; t < 600; t++)   // up to ~60 s for the ROM load + patch scan
    {
        run(e, 34);
        e->d(e, 7, 18, 0, disp, 0);   // patch_name
        if (disp[0] && std::strcmp(disp, "---") != 0 && t > 20) break;
    }
    e->setP(e, 19, 37.0f / 8191.0f);   // PATCH 37
    run(e, 400);
    e->setP(e, 3, 100.0f / 127.0f);    // CUTOFF 100 (macro)
    e->setP(e, 1, 90.0f / 127.0f);     // PATCH LVL 90 (NVRAM)
    run(e, 200);
    e->d(e, 7, 18, 0, disp, 0);
    std::printf("patch name: %s\n", disp);
    void* chunk = nullptr;
    const intptr_t n = e->d(e, 23, 0, 0, &chunk, 0);
    if (n <= 0 || !chunk) { std::fprintf(stderr, "no chunk\n"); return 1; }
    FILE* f = std::fopen(argv[2], "wb");
    std::fwrite(chunk, 1, (size_t)n, f);
    std::fclose(f);
    std::printf("wrote %s (%ld bytes): %.160s...\n", argv[2], (long)n, (const char*)chunk);
    e->d(e, 1, 0, 0, nullptr, 0);   // effClose
    return 0;
}
