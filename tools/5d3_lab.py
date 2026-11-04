#!/usr/bin/env python3
"""Preflight and run the 5D3 Magic Lantern camera-free development pipeline.

No camera connection is attempted. No physical SD/CF cards or camera firmware
are ever modified by this script. QEMU-EOS is a separate emulator requiring
an authorized local ROM0/ROM1 dump of the matching camera firmware.

Example:
    python3 tools/5d3_lab.py doctor
    python3 tools/5d3_lab.py unit
    python3 tools/5d3_lab.py --firmware 113 build
    python3 tools/5d3_lab.py --firmware 113 emulate --gdb

For real hardware performance, an actual camera test is still required.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
import zipfile
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
    # qemu-eos model_list.c: 5D3 ROM0=8 MiB, ROM1=16 MiB from DIGIC 5 defaults.
    # QEMU_EOS_WORKDIR/5D3 is the model directory; the first run must use
    # matching authentic ROMs, not the Magic Lantern installer/autoexec.
    _ = firmware
    roms = [(rom_root / "5D3" / "ROM0.BIN", 8 * 1024 * 1024),
            (rom_root / "5D3" / "ROM1.BIN", 16 * 1024 * 1024)]
    return (all(path.is_file() and path.stat().st_size == length
                for path, length in roms), [path for path, _ in roms])


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
    image = ROOT / "platform" / f"5D3.{args.firmware}" / "build" / "magiclantern.zip"
    print_check("QEMU firmware ZIP for virtual FAT card", image.is_file(), image)
    ptp_src = ROOT / "src" / "ptp-chdk.c"
    print_check("Optional USB PTP implementation", ptp_src.is_file(), ptp_src)
    print("\nNOTE: system/Homebrew qemu-system-arm is not a substitute for qemu-eos.")
    print("NOTE: no ROM dump was bundled with this repository.")
    print("NOTE: --boot uses isolated virtual FAT cards; no guestmount required.")
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
    if sys.platform == 'darwin':
        # The inherited build uses GNU stat syntax, incompatible with macOS.
        argv.append("STAT_CMD=stat -f '%N: %z bytes'")
    print("+", " ".join(argv), flush=True)
    if args.dry_run:
        return 0
    env = os.environ.copy()
    # Keep tools local to the repository and ARM SDK; avoid changing global PATH.
    local_tools = [ROOT / '.venv' / 'bin', arm_bin]
    env['PATH'] = os.pathsep.join([str(p) for p in local_tools if p.is_dir()] + [env.get('PATH', '')])
    return subprocess.call(argv, cwd=ROOT, env=env)


def emulate(args: argparse.Namespace) -> int:
    """Boot an isolated virtual FAT card without guestmount or a physical SD."""
    _, qemu_build, rom_dir, _ = config(args)
    qemu_bin = qemu_build / "arm-softmmu" / "qemu-system-arm"
    build_zip = ROOT / "platform" / f"5D3.{args.firmware}" / "build" / "magiclantern.zip"
    rom_ok, _ = check_roms(rom_dir, args.firmware)

    missing = []
    for name, exists in [
        ("Patched QEMU-EOS executable", qemu_bin.is_file()),
        ("5D3 8MiB ROM0.BIN and 16MiB ROM1.BIN", rom_ok),
        ("5D3 QEMU build magiclantern.zip", build_zip.is_file()),
    ]:
        if not exists:
            missing.append(name)
    if missing and not args.dry_run:
        print("Emulation not started; prerequisites missing:", file=sys.stderr)
        for name in missing:
            print("  -", name, file=sys.stderr)
        print("Run: python3 tools/5d3_lab.py doctor", file=sys.stderr)
        return 2

    # QEMU's vvfat device presents a regular host directory as a virtual FAT
    # card, removing the Linux guestmount dependency on Apple Silicon.
    # Any writes go only into these temporary directories.
    with tempfile.TemporaryDirectory(prefix="ml-5d3-virtual-cards-") as temp:
        base = Path(temp)
        sd = base / "sd"
        cf = base / "cf"
        sd.mkdir()
        cf.mkdir()
        if build_zip.is_file():
            with zipfile.ZipFile(build_zip) as archive:
                for member in archive.infolist():
                    dest = (sd / member.filename).resolve()
                    if not dest.is_relative_to(sd.resolve()):
                        raise ValueError("Unsafe path inside build ZIP")
                    if member.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(member) as src, dest.open("wb") as dst:
                            from shutil import copyfileobj
                            copyfileobj(src, dst)
        argv = [
            str(qemu_bin),
            "-M", "5D3,firmware=boot=1",
            "-drive", f"if=sd,format=raw,file=fat:rw:{sd}",
            "-drive", f"if=ide,format=raw,file=fat:rw:{cf}",
            "-display", "none",
            "-serial", "stdio",
            "-monitor", "none",
            "-no-reboot",
        ]
        if args.gdb:
            argv += ["-S", "-gdb", "tcp::1234"]
        env = os.environ.copy()
        env["QEMU_EOS_WORKDIR"] = str(rom_dir)
        print("+", " ".join(argv), flush=True)
        if args.dry_run:
            if missing:
                print("Dry-run only: " + "; ".join(missing) + " missing.")
            return 0
        return subprocess.call(argv, cwd=base, env=env)


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
