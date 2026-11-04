#!/usr/bin/env python3
"""
Offline comparison of Canon/Magic Lantern MMIO access logs.

Purpose: find *observed* register programming changes between two camera modes.
Never touches a camera, memory-mapped hardware, or firmware files. Accepts the
textual '[0xADDR] <- 0xVALUE' writes printed by Magic Lantern io_trace.c.
Avoids inferring capabilities from unobserved register writes.

Example:
    python3 tools/compare_mmio_traces.py stock_1080p.log stock_720p.log
    python3 tools/compare_mmio_traces.py stock_1080p.log high_res_liveview.log --json

The resulting differences ARE NOT hardware specifications. They identify
registers requiring disassembly and controlled experiments.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ACCESS = re.compile(
    r"\[\s*0x(?P<addr>[0-9a-fA-F]{8})\s*\]\s*"
    r"(?P<direction><-|->)\s*0x(?P<value>[0-9a-fA-F]{1,8})\b"
)


def classify(addr: int) -> str:
    # Ranges below: documented by Magic Lantern source; some names are provisional.
    if 0xC0E20000 <= addr < 0xC0E30000:
        return "JPCORE (likely encoder, exact register function unverified)"
    if 0xC0F04000 <= addr < 0xC0F05000:
        return "EDMAC channels bank 0 (0-15)"
    if 0xC0F05000 <= addr < 0xC0F06000:
        return "EDMAC connections/routing"
    if 0xC0F26000 <= addr < 0xC0F27000:
        return "EDMAC channels bank 1 (16-31)"
    if 0xC0F30000 <= addr < 0xC0F31000:
        return "EDMAC channels bank 2 (32-47)"
    if 0xC0F10000 <= addr < 0xC0F20000:
        return "Display/image-processing path (provisional)"
    if 0xC0F20000 <= addr < 0xC0F26000:
        return "Image-processing registers (provisional)"
    if 0xC0000000 <= addr < 0xE0000000:
        return "Other DIGIC MMIO (unclassified)"
    return "Not in known DIGIC MMIO map"


def read_log(file: Path, writes_only: bool) -> tuple[dict[int, list[int]], dict[str, int]]:
    out: dict[int, list[int]] = defaultdict(list)
    counts = {"lines": 0, "parsed": 0, "reads": 0, "writes": 0}
    with file.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            counts["lines"] += 1
            match = ACCESS.search(line)
            if not match:
                continue
            counts["parsed"] += 1
            direction = match.group("direction")
            counts["writes" if direction == "<-" else "reads"] += 1
            if writes_only and direction == "->":
                continue
            out[int(match.group("addr"), 16)].append(int(match.group("value"), 16))
    return out, counts


def compare(a: dict[int, list[int]], b: dict[int, list[int]]) -> list[dict]:
    records: list[dict] = []
    for addr in sorted(set(a) | set(b)):
        left = a.get(addr, [])
        right = b.get(addr, [])
        if Counter(left) == Counter(right):
            continue
        records.append({
            "address": f"0x{addr:08X}",
            "region": classify(addr),
            "a_count": len(left),
            "b_count": len(right),
            "a_distinct_values": [f"0x{v:08X}" for v in sorted(set(left))],
            "b_distinct_values": [f"0x{v:08X}" for v in sorted(set(right))],
            "a_last": f"0x{left[-1]:08X}" if left else None,
            "b_last": f"0x{right[-1]:08X}" if right else None,
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path, help="Baseline recording MMIO.LOG")
    parser.add_argument("b", type=Path, help="Comparison recording MMIO.LOG")
    parser.add_argument("--all-accesses", action="store_true", help="Include reads (default: writes only)")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON report")
    parser.add_argument("--region", choices=["jpcore", "edmac", "other", "all"], default="all")
    args = parser.parse_args()

    a, count_a = read_log(args.a, not args.all_accesses)
    b, count_b = read_log(args.b, not args.all_accesses)
    rows = compare(a, b)
    if args.region != "all":
        needle = {"jpcore": "JPCORE", "edmac": "EDMAC", "other": "Other"}[args.region]
        rows = [row for row in rows if row["region"].startswith(needle)]

    result = {
        "baseline": str(args.a),
        "comparison": str(args.b),
        "events_baseline": count_a,
        "events_comparison": count_b,
        "differing_addresses": len(rows),
        "observed_registers": rows,
        "caution": "Configuration delta only: no encoder maximum resolution or silicon throughput established.",
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Observed differing MMIO addresses: {len(rows)}")
    print(f"Input A: {count_a['parsed']} MMIO events ({count_a['writes']} writes)")
    print(f"Input B: {count_b['parsed']} MMIO events ({count_b['writes']} writes)")
    for row in rows:
        print(f"{row['address']} {row['region']}")
        print(f"    A: {row['a_count']} events, last={row['a_last']}, values={','.join(row['a_distinct_values'])}")
        print(f"    B: {row['b_count']} events, last={row['b_last']}, values={','.join(row['b_distinct_values'])}")
    print("\nCAUTION: Differences are not proof of hardware capability. Confirm with firmware disassembly and camera measurements.")


if __name__ == "__main__":
    main()
