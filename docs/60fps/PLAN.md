# 60 FPS on Wii — Plan

## Goal

Run Twilight Princess at a stable 60 FPS on Wii hardware.

1. **Performance:** an unlocked GameCube build running on Wii (via Nintendont, 729 MHz CPU) currently reaches ~45–60 FPS. Close the gap with targeted optimizations.
2. **Timing:** fix everything that assumes a 30 Hz game tick. Preferred approach: a native 60 Hz logic tick. Fallback: keep logic at 30 Hz and render with interpolation between ticks.

## Strategy

- **Develop against the GameCube build (`GZ2E01`)**, run on Wii via Nintendont. GameCube code is fully decompiled; the Wii builds (`RZDE01_*`) only have a handful of matching TUs, so source changes there would not reach the binary.
- Build with `--non-matching` so that functionally equivalent objects are linked from source.
- Revisit a native Wii build once the Wii decomp matures.

## Key code locations

| Area | Location |
| --- | --- |
| Frame pacing | `JFWDisplay::waitForTick` ([JFWDisplay.cpp](../../libs/JSystem/src/JFramework/JFWDisplay.cpp)), `mDoGph_gInf_c::setFrameRate` ([m_Do_graphic.h](../../include/m_Do/m_Do_graphic.h)) — game normally uses 2 (30 FPS) |
| Main loop | [m_Do_main.cpp](../../src/m_Do/m_Do_main.cpp) |
| Actor execution | `fpcM_Management` ([f_pc](../../src/f_pc/)) |
| Animation / skinning | [J3DGraphAnimator](../../libs/JSystem/src/J3DGraphAnimator/), [J3DTransform.cpp](../../libs/JSystem/src/J3DGraphBase/J3DTransform.cpp) |
| Collision | `dBgS` (`d_bg_*`), `dCcS` (`d_cc_*`) |
| Camera | [d_camera.cpp](../../src/d/d_camera.cpp) |
| Particles | JParticle (JPA), [d_particle.cpp](../../src/d/d_particle.cpp) |

## Phases

### Phase 0 — Buildable, modifiable GameCube baseline
- [x] Audit link status for `GZ2E01` (see Walkthrough)
- [x] Supply `orig/GZ2E01` disc image, build with `--non-matching`
- [x] Confirm the built DOL/RELs boot in Dolphin
- [ ] Resolve `d_menu_collect.cpp` (only remaining non-linked TU)
- [x] Confirm code can shift (add a dummy function, rebuild, boot)

### Phase 1 — Measurement
- [x] Add per-phase CPU timing (`--qol-perf`): frame, painter, execute, draw, cc, bg, particle, audio — untested in-game
- [x] Dolphin memory readout: `tools/perf_monitor.py`
- [x] On-screen overlay (L+R+Z on pad 1): last + 60-frame peak per section — untested in-game
- [ ] Finer sections inside execute/draw (J3D calc, per-actor-type costs)
- [ ] Determine CPU-bound vs GPU-bound per scene
- [ ] Baseline worst scenes on real hardware: Hyrule Field, Castle Town, Kakariko, heavy boss/particle scenes

### Phase 2 — Optimization (order driven by Phase 1 data)
Candidates:
- J3D: skip anim/matrix calc for culled or distant models; ensure paired-single matrix paths in hot loops
- Actor LOD: lower update rate / skip execute for distant actors
- Collision: spatial partitioning or caching in `dBgS` / `dCcS`
- Memory placement: check hot data in MEM1 vs MEM2 (Wii)
- Code layout: `-func_align`, hot/cold grouping once matching is no longer a constraint
- Strip leftover debug/assert work from release builds

### Phase 3 — 30 Hz → 60 Hz timing
Decide between native 60 Hz logic vs interpolated rendering once Phase 2 headroom is known.

Native 60 Hz checklist:
- [ ] Per-frame velocities/gravity (`speedF`, `gravity`, accelerations) — halve; drag multipliers become `sqrt(k)`
- [ ] Frame-count timers and counters — double
- [ ] Animation play speed (`setPlaySpeed`, `getBaseAnimeFrameRate`) — halve
- [ ] Fixed-factor interpolation (camera smoothing, slerps like `0.25f`) — `1 - sqrt(1 - k)`
- [ ] `g_Counter` and RNG usage keyed to frame count
- [ ] JPA particle emission rates / lifetimes
- [ ] Audio-synced events, cutscenes (JStudio demo timing), movie player
- [ ] Physics/tricks regression pass

### Phase 4 — Validation
- [ ] Full-playthrough regression tests on key sequences
- [ ] Performance soak on hardware
