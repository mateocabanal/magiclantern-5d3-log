#!/usr/bin/env python3
"""Preflight and run the 5D3 Magic Lantern camera-free development pipeline.

No camera connection is attempted. No physical SD/CF cards or camera firmware
are ever modified by this script. QEMU-EOS is a separate emulator requiring
an authorized local ROM0/ROM1 dump of the matching camera firmware.

Example:
    python3 tools/5d3_lab.py doctor
    python3 tools/5d3_lab.py unit
    python3 tools/5d3_lab.py build --firmware 113
    python3 tools/5d3_lab.py emulate --firmware 113 --gdb

For real hardware performance, an actual camera test is still required.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = ROOT.parent
DEFAULT_QEMU_SRC = DEV_ROOT / "qemu-eos"
DEFAULT_QEMU_BUILD = DEV_ROOT / "qemu-eos-build"
DEFAULT_ROM_DIR = DEV_ROOT / "roms"
DEFAULT_ARM_BIN = DEV_ROOT / "_toolchains" / "arm-gnu-toolchain-14.3.rel1-darwin-arm64-arm-none-eabi" / "bin"


def config(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    return (Path(args.qemu_src).expanduser().resolve(),
            Path(args.qemu_build).expanduser().resolve(),
            Path(args.rom_dir).expanduser().resolve(),
            Path(args.arm_bin).expanduser().resolve())


def print_check(label: str, condition: bool, location: Path | str) -> None:
    print(f"{'OK  ' if condition else 'MISS'} {label}: {location}")


def check_roms(rom_root: Path, firmware: str) -> tuple[bool, list[Path]]:
    # QEMU-EOS reads QEMU_EOS_WORKDIR/5D3/ or /5D3/<firmware>/.
    # Firmware-version directory naming depends on QEMU-EOS model settings.
    dirs = [rom_root / "5D3" / ("1.1.3" if firmware == "113" else "1.2.3"),
            rom_root / "5D3",
            rom_root]
    for directory in dirs:
        files = [directory / "ROM0.BIN", directory / "ROM1.BIN"]
        if all(f.is_file() and f.stat().st_size > 0 for f in files):
            return True, files
    return False, [rom_root / "5D3" / "ROM0.BIN", rom_root / "5D3" / "ROM1.BIN"]


def doctor(args: argparse.Namespace) -> int:
    qemu_src, qemu_build, rom_dir, arm_bin = config(args)
    print("5D3 LOG engineering lab: preflight only; no hardware accesses\n")
    path = arm_bin / "arm-none-eabi-gcc"
    print_check("ARM cross-compiler", path.is_file(), path)
    print_check("Magic Lantern 5D3 sources", (ROOT / "platform" / f"5D3.{args.firmware}").is_dir(),
                ROOT / "platform" / f"5D3.{args.firmware}")
    runner = qemu_src / "magiclantern" / "run_qemu.py"
    print_check("Patched QEMU-EOS runner", runner.is_file(), runner)
    qemu_bin = qemu_build / "arm-softmmu" / "qemu-system-arm"
    print_check("Patched EOS emulator", qemu_bin.is_file(), qemu_bin)
    present, files = check_roms(rom_dir, args.firmware)
    print_check("Actual Canon ROM0/ROM1", present, ", ".join(map(str, files)))
    image = ROOT / "platform" / f"5D3.{args.firmware}" / "build" / "sd.qcow2"
    print_check("QEMU SD image", image.is_file(), image)
    ptp_src = ROOT / "src" / "ptp-chdk.c"
    print_check("Optional USB PTP implementation", ptp_src.is_file(), ptp_src)
    print("\nNOTE: system/Homebrew qemu-system-arm is not a substitute for qemu-eos.")
    print("NOTE: no ROM dump was bundled with this repository.")
    if not present:
        print("To boot real Canon firmware, obtain authorized matching ROM0/ROM1 dumps; a ML installer FIR or autoexec.bin is not a full ROM dump.")
    if not runner.is_file() or not qemu_bin.is_file():
        print("QEMU-EOS (Linux-tested): https://github.com/reticulatedpines/qemu-eos")
        print("Upstream instructions: qemu-eos/magiclantern/README.md (branch qemu-eos-v4.2.1)")
    return 0


def run_unit(_: argparse.Namespace) -> int:
    return subprocess.call([sys.executable, "-m", "unittest", "discover",
                            "-s", "tests", "-p", "test_*.py", "-v"], cwd=ROOT)


def build(args: argparse.Namespace) -> int:
    _, _, _, arm_bin = config(args)
    cc = arm_bin / "arm-none-eabi-gcc"
    if not cc.is_file():
        print(f"Missing cross-compiler: {cc}", file=sys.stderr)
        return 2
    directory = ROOT / "platform" / f"5D3.{args.firmware}"
    argv = ["make", "-C", str(directory),
            f"ARM_BINPATH={arm_bin}",
            "CONFIG_QEMU=y" if args.qemu else "CONFIG_QEMU=n",
            f"-j{args.jobs}"]
    print("+", " ".join(argv), flush=True)
    if args.dry_run:
        return 0
    return subprocess.call(argv, cwd=ROOT)


def emulate(args: argparse.Namespace) -> int:
    qemu_src, qemu_build, rom_dir, _ = config(args)
    runner = qemu_src / "magiclantern" / "run_qemu.py"
    qemu_bin = qemu_build / "arm-softmmu" / "qemu-system-arm"
    image = ROOT / "platform" / f"5D3.{args.firmware}" / "build" / "sd.qcow2"
    rom_ok, paths = check_roms(rom_dir, args.firmware)

    missing = []
    for name, exists in [
        ("QEMU-EOS runner", runner.is_file()),
        ("Patched QEMU-EOS executable", qemu_bin.is_file()),
        ("5D3 ROM0.BIN and ROM1.BIN", rom_ok),
        ("ML build SD image (make disk_image)", image.is_file()),
    ]:
        if not exists:
            missing.append(name)
    if missing:
        print("Emulation not started; prerequisites missing:", file=sys.stderr)
        for x in missing:
            print("  -", x, file=sys.stderr)
        print("Run: python3 tools/5d3_lab.py doctor", file=sys.stderr)
        return 2

    # run_qemu.py chooses the FIRST matching platform dir for '5D3' and
    # may choose the other firmware; refuse to allow an unsafe ambiguity.
    path113 = ROOT / "platform" / "5D3.113"
    path123 = ROOT / "platform" / "5D3.123"
    if path113.is_dir() and path123.is_dir():
        print("WARNING: upstream run_qemu.py searches by model prefix '5D3',", file=sys.stderr)
        print("so the firmware-version folder selected is not guaranteed.", file=sys.stderr)
        print("Use an explicit model-specific checkout or fix the upstream runner", file=sys.stderr)
        print("to select the correct 5D3.<firmware> platform before first boot.", file=sys.stderr)
        return 2

    command = [sys.executable, str(runner), "5D3",
               "-q", str(qemu_build), "-r", str(rom_dir),
               "-s", str(ROOT), "--boot"]
    if args.gdb:
        command.append("--gdb")
    print("+", " ".join(command), flush=True)
    if args.dry_run:
        return 0
    return subprocess.call(command, cwd=runner.parent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--qemu-src", default=str(DEFAULT_QEMU_SRC))
    parser.add_argument("--qemu-build", default=str(DEFAULT_QEMU_BUILD))
    parser.add_argument("--rom-dir", default=str(DEFAULT_ROM_DIR))
    parser.add_argument("--arm-bin", default=str(DEFAULT_ARM_BIN))
    parser.add_argument("--firmware", choices=["113", "123"], default="113")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("doctor", help="Check dependencies; never touches hardware")
    commands.add_parser("unit", help="Run offline parser and analysis unit tests")
    build_parser = commands.add_parser("build", help="Compile an emulator-specific Magic Lantern build")
    build_parser.add_argument("--jobs", type=int, choices=range(1, 17), metavar="N", default=2)
    build_parser.add_argument("--camera", action="store_false", dest="qemu", help="Build for physical camera instead of QEMU")
    build_parser.add_argument("--dry-run", action="store_true")
    run_parser = commands.add_parser("emulate", help="Run a prepared QEMU-EOS 5D3 firmware")
    run_parser.add_argument("--gdb", action="store_true")
    run_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.action == "doctor":
        return doctor(args)
    if args.action == "unit":
        return run_unit(args)
    if args.action == "build":
        return build(args)
    if args.action == "emulate":
        return emulate(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
