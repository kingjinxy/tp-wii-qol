# 60 FPS on Wii — Running Walkthrough

Chronological log of work, findings, and decisions. Newest entries at the bottom. See [PLAN.md](PLAN.md) for the overall plan.

---

## 2026-10-12 — Initial survey

- Wii versions have only ~7 TUs marked matching in `configure.py`; ~1,240 are `MatchingFor(ALL_GCN…)`. **Decision:** develop on `GZ2E01`, run on Wii via Nintendont.
- Frame pacing: `JFWDisplay::waitForTick(mTickRate, mFrameRate)`; game normally sets frame rate 2 (30 FPS). The movie player sets 1.

## 2026-10-12 — GZ2E01 link audit

**Question:** Does the GameCube build link entirely from source?

**Method:** Gathered every `Object`/`ActorRel` in `configure.py` whose status is not matching for GCN. Then filtered to TUs that actually exist in `config/GZ2E01/splits.txt` (most are Wii SDK, Shield, or debug-only and are not in the GCN DOL).

**Result:** All REL actors are linked; 16 of them are `Equivalent` (they link with `--non-matching`). In the DOL, all TUs are linked except:

| TU | Status | Reason (from configure.py) |
| --- | --- | --- |
| `d/d_particle.cpp` | Equivalent | weak func order |
| `d/d_cc_d.cpp` | Equivalent | weak func order |
| `d/actor/d_a_alink.cpp` | Equivalent | weak func order, vtable order |
| `d/d_camera.cpp` | Equivalent | weak func order |
| `d/d_menu_window.cpp` | Equivalent | weak func order |
| `d/d_msg_object.cpp` | Equivalent | weak func order |
| `JSystem/JAudio2/JASTrack.cpp` | Equivalent | weak func order |
| `JSystem/J3DGraphBase/J3DMatBlock.cpp` | Equivalent | weak func order |
| `d/d_menu_collect.cpp` | **NonMatching** | weak func order (`dMenu_Collect2D_c::draw()`) |

"Weak func order" only affects where inline/weak functions land in the object, not behavior. With `python3 configure.py --non-matching`, **everything except `d_menu_collect.cpp` links from source.** Several of these files (alink, camera, collision, particles) are ones we'll need to modify, so `--non-matching` is mandatory for this project.

**Not verified yet:** No actual build was run because `orig/GZ2E01/` is empty (disc image required).

**Next:**
1. Place the GZ2E01 image in `orig/GZ2E01/`, run `python3 configure.py --non-matching && ninja`, and boot the result.
2. Try switching `d_menu_collect.cpp` to `Equivalent` and test the collection screen.
3. Shift test: add code to an early TU and confirm the game still boots (verifies relocations/pointers aren't hardcoded).

## 2026-10-12 — First `--non-matching` build

- Disc image: `orig/GZ2E01/*.rvz` (RVZ accepted directly, no ISO conversion needed).
- `python3 configure.py --non-matching && ninja` → builds `build/GZ2E01/framework.dol` + 758 RELs. Re-running `ninja` reports no work to do.
- Linker emits many harmless `FORCEACTIVE symbol ... doesn't exist. Ignored.` warnings.
- `d_menu_collect.cpp` is still taken from the original object (not yet switched to `Equivalent`).

**Next:** Pack the built DOL/RELs into a bootable image and boot in Dolphin; then the `d_menu_collect` and shift tests.

## 2026-10-12 — Packing a bootable ISO

- `tools/rebuild-decomp-tp.py` needs [gclib](https://github.com/LagoLunatic/gclib) (cloned to `tools/gclib`, git-excluded via `.git/info/exclude`), an ISO input, and a `--map` build.
- `dolphin-tool convert -f iso` → `build/GZ2E01_vanilla.iso`.
- Script modified: RELs in `RELS.arc` are compressed with `build/tools/dtk yaz0 compress` instead of gclib's pure-Python Yaz0. Byte-identical RELs keep the original data, but because the non-matching DOL differs from vanilla, every REL's DOL relocations change, so all 134 get recompressed anyway. Total run: ~0.4s.
- Verified: `build/GZ2E01_mod.iso` has the same 3760 files as vanilla, `sys/main.dol` == `framework.dol`, and every recompressed REL decompresses to the built REL. The output is smaller than vanilla (1.05 vs 1.46 GB) only because gclib doesn't pad to full disc size.
- Map copied to `~/.local/share/dolphin-emu/Maps/GZ2E01.map` for Dolphin symbols.

Rebuild loop: `ninja && python3 tools/rebuild-decomp-tp.py build/GZ2E01_vanilla.iso build/GZ2E01_mod.iso . --map ~/.local/share/dolphin-emu/Maps`

## 2026-10-12 — Boot test

- `build/GZ2E01_mod.iso` boots and runs in Dolphin (in the dev VM; slow, but fine for correctness). Faster test setups are being explored.

## 2026-10-12 — Shift test: PASS

- Added `qolShiftTest()` + `qolShiftTestCounter` in `m_Do_main.cpp`, called each frame. Shifts `main01` and all later `.text` by 0x10 and also shifts data. ISO boots and plays normally. Code can be freely added.
- Found `JUTProcBar` is fully active in retail: it measures CPU, GP, GP wait, idle, whole loop and cost-in-retraces each frame, and has 8 spare user timers (`mUsers[8]`). Only the on-screen draw is gated (devmode + pad 3 + HIO meter flag, `mDoGph_AfterOfDraw`).

## 2026-10-12 — Frame profiler (`--qol-perf`)

Shift test code removed and replaced with a real profiler, compiled only with `python3 configure.py --non-matching --map --qol-perf`.

- `include/qol/qol_perf.h`: `QOL_PERF_START/END(section)` macros (no-ops without `QOL_PERF`), `qolPerf_c g_qolPerf` layout with fixed offsets for external readers. Times are raw `OSGetTick()` ticks; `mBusClock` holds the runtime `OS_BUS_CLOCK` (matters for Nintendont, where clocks differ from GCN).
- Implementation lives in `m_Do_main.cpp`, because adding a new TU would need splits changes. `qolPerf_frameEnd()` publishes the last frame (`mCur`) and the worst over 60 frames (`mPeak`), plus VI retraces per frame.
- Sections: frame, painter (`cAPIGph_Painter`, includes vsync/GPU waits), execute (`fpcEx_Handler`, includes cc/bg/particle), draw (`fpcDw_Handler`), cc (`dCcS::Move`), bg (`dBgS::Move`), particle (calc3D+2D), audio.
- Overlay: hold L+R on pad 1 and press Z. Text via `JUTReport`, plus forces the `JUTProcBar` bar visible (`mDoGph_AfterOfDraw`).
- `tools/perf_monitor.py`: reads `g_qolPerf` and `JUTProcBar` (idle/gp/cpu/gpwait/whole, cost_frames) from Dolphin via `dolphin-memory-engine` (installed in `.venv/`, git-excluded). Optional `--csv`.

Run: `.venv/bin/python tools/perf_monitor.py [--csv perf.csv]` while the game runs in Dolphin.

**Status:** Builds; symbols resolve (`g_qolPerf` @ 0x803A339C). Untested in-game.

## 2026-10-12 — First Dolphin readout + runtime FPS unlock

- `perf_monitor.py` works against Dolphin (light scene, 30 FPS cap): frame 33.2 ms, painter 29 ms (~24 ms of it idle on vsync), execute 1.8 ms, draw 2.4 ms, cc/bg/particle < 0.3 ms, audio < 0.1 ms; JUTProcBar gp ~9.2 ms, cpu ~4.5 ms. Bus 162 MHz (Dolphin GCN). Dolphin ran at ~2/3 speed in the VM.
- The 30 FPS cap is `setTickRate(OS_TIMER_CLOCK / 30)` in `d_s_play.cpp` and `d_s_name.cpp` (logo/menu use /60). It is not `setFrameRate`; the movie player is the only `setFrameRate(1)` user.
- Added a runtime unlock (`--qol-perf` builds only): **L+R+X** on pad 1 toggles it. The `mDoGph_gInf_c::setTickRate/setFrameRate` wrappers record the requested rate; when unlocked, a 30 Hz tick request becomes 60 Hz. Game logic runs at double speed while unlocked; this is for profiling only. `g_qolPerf` is now version 2 (`mUnlock` @ 0xC5, `mRequestedTickRate` @ 0xC8); the monitor shows/logs `UNLOCKED`.

## 2026-10-12 — Unlock works (light scene)

- Unlocked in Dolphin: retraces 1 (peak 1), frame ~16.6–17.0 ms, idle ~7–8 ms, gp ~8.5–9.6 ms, cpu ~3.4–4.2 ms, execute ~1.7 ms, draw ~1.8–2.8 ms. The light scene holds 60 in emulated GCN timing (162 MHz) with ~7 ms to spare.
- Dolphin's wall-clock rate was ~20 FPS (VM emulation speed), so real-time feel in the VM is not representative.
- Next: tour heavy scenes (Hyrule Field, Castle Town, Kakariko, particle-heavy bosses) with `--csv`.

## 2026-10-12 — Warp menu for profiling

- Retail disc lacks the debug stage-select data (`/res/Menu/Menu1.dat`), so spawn points were read directly from `PLYR` chunks in each room's `.dzr` (`res/Stage/<stage>/Rxx_00.arc`). A spawn point number matches `(u8)angle.z` (`dStage_playerInit`). Point 0 exists in every room checked.
- `--qol-perf` builds: with the overlay open, hold L+R and press D-pad Left/Right to pick a destination, then D-pad Up to warp (`dComIfGp_setNextStage(stage, point, room, -1)`; layer -1 = story-progress default). Only fires when a player actor exists.
- Destinations: Hyrule Field (F_SP121) rooms 0/3/6/7/10/13, Castle Town (F_SP116) rooms 0/1/3, Kakariko (F_SP109) room 0. All point 0. Untested in-game.
