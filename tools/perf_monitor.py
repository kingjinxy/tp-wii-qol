#!/usr/bin/env python3
"""
Live readout of the QOL frame profiler (g_qolPerf) and JUTProcBar from a running Dolphin.

Requires a build configured with `--non-matching --map --qol-perf` and the
dolphin-memory-engine package (`.venv/bin/pip install dolphin-memory-engine`).

Usage:
  .venv/bin/python tools/perf_monitor.py [--version GZ2E01] [--interval 0.5] [--csv out.csv]

Note: times read in Dolphin reflect emulated timing, not real hardware. Use them for
relative comparisons; confirm absolute numbers on a Wii.
"""

import argparse
import csv
import re
import struct
import sys
import time
from pathlib import Path

import dolphin_memory_engine as dme

SECTIONS = ["frame", "painter", "execute", "draw", "cc", "bg", "particle", "audio"]
NUM_SECTIONS = len(SECTIONS)
QOL_PERF_MAGIC = 0x51505246
QOL_PERF_VERSION = 2
QOL_PERF_UNLOCK_OFFSET = 0xC5
QOL_PERF_HEADER_SIZE = 0x18
QOL_PERF_READ_SIZE = QOL_PERF_HEADER_SIZE + NUM_SECTIONS * 4 * 2  # header, mCur, mPeak

# JUTProcBar::CTime blocks: offset of the block within JUTProcBar; mCost (us) is at +0x04
PROCBAR_TIMES = [("pb_idle", 0x00), ("pb_gp", 0x14), ("pb_cpu", 0x28), ("pb_gpwait", 0x3C), ("pb_whole", 0x50)]
PROCBAR_COST_FRAME = 0x104


def find_symbol(map_path: Path, name: str) -> int:
    pattern = re.compile(r"^\s+[0-9a-f]+ [0-9a-f]+ ([0-9a-f]{8}) [0-9a-f]+\s+\d+ " + re.escape(name) + r"\s")
    with open(map_path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                return int(m.group(1), 16)
    sys.exit(f"Symbol {name} not found in {map_path}. Was the build configured with --map --qol-perf?")


def hook():
    while not dme.is_hooked():
        dme.hook()
        if not dme.is_hooked():
            print("Waiting for Dolphin (game must be running)...", end="\r", flush=True)
            time.sleep(1)
    print(" " * 60, end="\r")


def ticks_to_us(ticks: int, bus_clock: int) -> float:
    return ticks * 1_000_000 / (bus_clock / 4) if bus_clock else 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", default="GZ2E01")
    parser.add_argument("--interval", type=float, default=0.5, help="seconds between samples")
    parser.add_argument("--csv", type=Path, help="also append every sample to this CSV file")
    args = parser.parse_args()

    map_path = Path(__file__).parent.parent / "build" / args.version / "framework.elf.MAP"
    perf_addr = find_symbol(map_path, "g_qolPerf")
    procbar_ptr_addr = find_symbol(map_path, "sManager__10JUTProcBar")

    hook()
    magic, version = struct.unpack(">II", dme.read_bytes(perf_addr, 8))
    if magic != QOL_PERF_MAGIC or version != QOL_PERF_VERSION:
        sys.exit(f"g_qolPerf at {perf_addr:08X} has magic {magic:08X} version {version}; "
                 "is the running game the same build as the map?")

    csv_writer = None
    if args.csv:
        csv_file = open(args.csv, "a", newline="")
        csv_writer = csv.writer(csv_file)
        if csv_file.tell() == 0:
            csv_writer.writerow(["time", "frame_count", "unlocked", "retraces", "peak_retraces"]
                                + [f"{s}_us" for s in SECTIONS] + [f"{s}_peak_us" for s in SECTIONS]
                                + [name + "_us" for name, _ in PROCBAR_TIMES] + ["pb_cost_frames"])

    last_frame = None
    try:
        while True:
            if not dme.is_hooked():
                hook()

            data = dme.read_bytes(perf_addr, QOL_PERF_READ_SIZE)
            _, _, bus_clock, frame_count, retraces, peak_retraces = struct.unpack(">6I", data[:QOL_PERF_HEADER_SIZE])
            words = struct.unpack(f">{NUM_SECTIONS * 2}I", data[QOL_PERF_HEADER_SIZE:])
            cur = [ticks_to_us(t, bus_clock) for t in words[:NUM_SECTIONS]]
            peak = [ticks_to_us(t, bus_clock) for t in words[NUM_SECTIONS:]]

            procbar = dme.read_word(procbar_ptr_addr)
            pb = [dme.read_word(procbar + off + 4) for _, off in PROCBAR_TIMES] if procbar else [0] * len(PROCBAR_TIMES)
            pb_cost_frames = dme.read_word(procbar + PROCBAR_COST_FRAME) if procbar else 0

            unlocked = dme.read_byte(perf_addr + QOL_PERF_UNLOCK_OFFSET)

            fps = ""
            if last_frame is not None:
                fps = f"{(frame_count - last_frame[0]) / (time.monotonic() - last_frame[1]):5.1f} fps"
            last_frame = (frame_count, time.monotonic())

            lines = [f"frame {frame_count}  retraces {retraces} (peak {peak_retraces})  {fps}  bus {bus_clock / 1e6:.1f} MHz"
                     + ("  UNLOCKED" if unlocked else ""),
                     f"{'section':<10}{'last us':>10}{'peak us':>10}"]
            lines += [f"{s:<10}{c:>10.0f}{p:>10.0f}" for s, c, p in zip(SECTIONS, cur, peak)]
            lines.append("JUTProcBar: " + "  ".join(f"{name[3:]} {v}" for (name, _), v in zip(PROCBAR_TIMES, pb))
                         + f"  cost_frames {pb_cost_frames}")
            print("\x1b[H\x1b[J" + "\n".join(lines), flush=True)

            if csv_writer:
                csv_writer.writerow([f"{time.time():.3f}", frame_count, unlocked, retraces, peak_retraces]
                                    + [f"{v:.0f}" for v in cur + peak] + pb + [pb_cost_frames])

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
