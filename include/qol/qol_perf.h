#ifndef QOL_PERF_H
#define QOL_PERF_H

/**
 * QOL frame profiler. Enabled with `configure.py --non-matching --qol-perf`.
 *
 * Times are raw OSGetTick() ticks (OS_BUS_CLOCK / 4 per second). The state lives in a single
 * global, g_qolPerf, so external tools (tools/perf_monitor.py) can read it from emulator memory.
 * In-game overlay: hold L + R on controller 1 and press Z.
 * Frame rate unlock (30 -> 60 tick rate, game logic runs at double speed): hold L + R and press X.
 */

#if QOL_PERF

#include <os.h>

enum qolPerf_Section {
    QOL_PERF_FRAME,    // one main loop iteration
    QOL_PERF_PAINTER,  // cAPIGph_Painter: GX submission of draw lists, incl. vsync and GPU waits
    QOL_PERF_EXECUTE,  // fpcEx_Handler: all process execute (includes CC, BG and PARTICLE)
    QOL_PERF_DRAW,     // fpcDw_Handler: all process draw (draw list building, J3D calc)
    QOL_PERF_CC,       // dCcS::Move (object collision)
    QOL_PERF_BG,       // dBgS::Move (background collision)
    QOL_PERF_PARTICLE, // particle calc3D + calc2D
    QOL_PERF_AUDIO,    // mDoAud_Execute
    QOL_PERF_MAX
};

#define QOL_PERF_MAGIC 0x51505246 // 'QPRF'
#define QOL_PERF_VERSION 2
#define QOL_PERF_PEAK_WINDOW 60

struct qolPerf_c {
    /* 0x00 */ u32 mMagic;
    /* 0x04 */ u32 mVersion;
    /* 0x08 */ u32 mBusClock;
    /* 0x0C */ u32 mFrameCount;
    /* 0x10 */ u32 mRetraces;     // VI retraces taken by the last frame
    /* 0x14 */ u32 mPeakRetraces; // worst mRetraces over the last peak window
    /* 0x18 */ u32 mCur[QOL_PERF_MAX];  // last frame, ticks
    /* 0x38 */ u32 mPeak[QOL_PERF_MAX]; // worst over the last peak window, ticks
    /* 0x58 */ u32 mAccum[QOL_PERF_MAX]; // current frame in progress, ticks
    /* 0x78 */ u32 mStart[QOL_PERF_MAX];
    /* 0x98 */ u32 mWindowPeak[QOL_PERF_MAX];
    /* 0xB8 */ u32 mWindowPeakRetraces;
    /* 0xBC */ u32 mWindowFrames;
    /* 0xC0 */ u32 mLastRetrace;
    /* 0xC4 */ u8 mOverlay;
    /* 0xC5 */ u8 mUnlock;
    /* 0xC8 */ u32 mRequestedTickRate; // last tick rate the game asked for; 0 while in frame rate mode
};

extern qolPerf_c g_qolPerf;

void qolPerf_frameEnd();
bool qolPerf_isOverlay();
u32 qolPerf_adjustTickRate(u32 rate);

inline void qolPerf_start(int section) {
    g_qolPerf.mStart[section] = OSGetTick();
}

inline void qolPerf_end(int section) {
    g_qolPerf.mAccum[section] += OSGetTick() - g_qolPerf.mStart[section];
}

#define QOL_PERF_START(section) qolPerf_start(section)
#define QOL_PERF_END(section) qolPerf_end(section)

#else

#define QOL_PERF_START(section)
#define QOL_PERF_END(section)

#endif

#endif /* QOL_PERF_H */
