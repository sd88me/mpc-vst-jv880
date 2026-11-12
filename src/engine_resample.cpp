// libresample (src/dsp/resample/*.c, BSD/LGPL as vendored): only closed by the engine, but it must link. C code compiled as C++.
extern "C" {
#include "dsp/resample/resample.c"
#include "dsp/resample/resamplesubs.c"
#include "dsp/resample/filterkit.c"
}
