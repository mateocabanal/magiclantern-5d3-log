# 5D Mark III camera-free development environment

Status: **QEMU-EOS core built and verified on Apple Silicon; Canon firmware boot pending authorized ROM dumps** (November 3, 2026).

## Locations

- Project: `~/CODE/magiclantern-5d3-log`, branch `feature/5d3-log-video`.
- Canon-specific QEMU sources: `~/CODE/qemu-eos`, branch `qemu-eos-v4.2.1`.
- Patched emulator executable: `~/CODE/qemu-eos-build/arm-softmmu/qemu-system-arm`.
- ARM cross toolchain: `~/CODE/_toolchains/arm-gnu-toolchain-14.3.rel1-darwin-arm64-arm-none-eabi/bin`.
- Project-local Python build tools: `.venv` (docutils, Pillow).
- Validated 5D3.113 `CONFIG_QEMU=y` firmware ZIP: `platform/5D3.113/build/magiclantern.zip`.

## Confirmed completed

1. QEMU-EOS cloned and configured on macOS ARM64. The original plugin-enabled build failed at link time with unexported `qemu_plugin_*` symbols. A reconfiguration with **plugins disabled**, plus disabled Nettle/GnuTLS due incompatible current Nettle headers, built successfully.
2. Ran the patched QEMU executable: reports **QEMU 4.2.1**.
3. Ran `-machine help`: **Canon EOS 5D3** is listed.
4. Built Magic Lantern **5D3 firmware 1.1.3 for QEMU** successfully. This is not physical-camera firmware.
5. Improved `tools/5d3_lab.py`: ARM SDK and Python venv in PATH, macOS BSD `stat` override, ROM size checks, and virtual FAT card extraction from compiled ML ZIP. No on-camera upload or camera operation.

## Daily commands

```sh
cd ~/CODE/magiclantern-5d3-log

python3 tools/5d3_lab.py doctor
python3 tools/5d3_lab.py unit
python3 tools/5d3_lab.py --firmware 113 build --jobs 2

# Once matching ROM dumps are available:
python3 tools/5d3_lab.py --firmware 113 emulate
# Optional CPU remote-debugger entry; requires a GDB client:
python3 tools/5d3_lab.py --firmware 113 emulate --gdb
```

Note that emulator launch uses temporary host **virtual FAT directories** via QEMU's `fat:rw:` driver, not physical cards or Linux `guestmount`. This code path is currently **dry-run checked only**, since the Canon ROM is missing. Do not treat it as proven to boot before the real ROM test.

## Missing ROM files

QEMU-EOS's `hw/eos/model_list.c` lists the 5D3 with 8 MiB `ROM0`, and DIGIC 5 defaults to 16 MiB `ROM1`. The lab currently requires:

```text
~/CODE/roms/5D3/ROM0.BIN   # exactly 8,388,608 bytes
~/CODE/roms/5D3/ROM1.BIN   # exactly 16,777,216 bytes
```

These must be genuine, compatible camera firmware dumps, obtained lawfully from an authorized device. The `ML-SETUP.FIR`, `AUTOEXEC.BIN`, or Canon update `.FIR` should **not** be renamed to `ROM0.BIN`/`ROM1.BIN`. This project does not include or upload Canon ROM images.

The 5D3 supports both firmware 1.1.3 and 1.2.3 in the ML source tree, with different ROM function addresses. The current build targets **1.1.3**. Version validation must be performed before actual camera testing.

## What QEMU-EOS does NOT simulate

The emulator's `hw/eos/engine.c` identifies JP51 (JPEG), JP62 (H.264), JP57 (newer lossless) and EDMAC memory-mapped IO. Its JPCORE handler largely logs register writes and synthesizes interrupts; **it does not simulate true H.264 codec throughput**. Therefore, successful emulation cannot establish the 5D3's maximum supported compression dimensions.

QEMU is useful for register driver state, memory layout, boot regressions, integration with Magic Lantern, GDB, virtual cards, and simulated error cases. Determining >1080p H.264 or sustained MJPEG capacity still requires real hardware traces/experiments or authoritative chip documentation.

## Related source code

- Emulator: https://github.com/reticulatedpines/qemu-eos/tree/qemu-eos-v4.2.1
- Engine MMIO: https://github.com/reticulatedpines/qemu-eos/blob/qemu-eos-v4.2.1/hw/eos/engine.c
- EOS 5D3 model: https://github.com/reticulatedpines/qemu-eos/blob/qemu-eos-v4.2.1/hw/eos/model_list.c
- Our lab script: `tools/5d3_lab.py`
- Offline trace analyzer: `tools/compare_mmio_traces.py`

## Apple Silicon JIT compatibility fix

This old QEMU tree initially failed on macOS ARM64 at runtime with `Could not allocate dynamic translator buffer`. The project patch `patches/qemu-eos-apple-silicon-map-jit.patch` requests `MAP_JIT` when allocating the TCG translation buffer on Apple Silicon. Apply it in `~/CODE/qemu-eos` with `git apply ../magiclantern-5d3-log/patches/qemu-eos-apple-silicon-map-jit.patch` before building. Our local QEMU checkout is already patched on branch `macos-arm64-jit`.

A post-patch smoke test started the `5D3` machine in **paused** (`-S`) mode with two temporary `fat:rw:` virtual cards and no error output. The test ended by a bounded host timeout (normal for a paused VM). It demonstrates successful TCG allocation and device setup, **not execution of Canon firmware, JIT translations under load, or codec emulation fidelity**.

The old QEMU plugin-enabled build also failed at link time on Apple Silicon (`qemu_plugin_*` exports). The successful native build was configured with `--disable-plugins --disable-nettle --disable-gnutls`. The QEMU GDB stub remains available independently of plugins.
