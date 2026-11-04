# EOS 5D Mark III: high-resolution compressed LOG video feasibility

Status: **research / unproven on-camera** (2026-11-03)
Camera: Canon EOS 5D Mark III; DIGIC 5+; Magic Lantern platforms **5D3.113 / 5D3.123**.
Scope: feasibility of sensor -> high-resolution image processing -> logarithmic transfer curve -> hardware-compressed video; **not** an existing Canon Picture Style feature.

## Executive assessment

**There is no identified programmable GPU in public documentation for this camera.** DIGIC 5+ (identified as Canon **CH4-6501**) is a proprietary image-processing SoC, not a desktop/mobile GPU exposing shaders or compute APIs. An ARMv5TE CPU executes Canon DryOS and Magic Lantern, alongside fixed-function imaging, DMA and compression blocks. Public Magic Lantern documentation does not enumerate the full accelerator microarchitecture or publish a maximum supported H.264 encoder frame size.

The sensor **can** be driven at >1080p RAW capture modes (e.g. 3072x1920@24, 3840x1600@24 and 4096x1440@25 in experimental builds). This **does not establish** that Canon's demosaic/ISP path or H.264 codec can handle those geometries. Existing 5D3 H.264 is up to 1920x1080/30 in Canon firmware; Canon's hardware implements ALL-I and IPB.

**LOG is a tonal transfer function, not video compression.** File-size savings would come from a lossy compressor (H.264) or an alternative compression algorithm, not from LOG by itself. A LOG encoding in an 8-bit 4:2:0 H.264 workflow can lose tonal and chroma precision even if it makes grading easier. The exact native processing bit depth through 5D3 hardware encoder remains a research question.

## Relevant blocks and source entry points

| Block | Evidence | Implication |
|---|---|---|
| Sensor + readout | Canon specifies 22.3MP and eight-channel readout; experimental crop_rec high-res RAW modes | Test bandwidth and sensor timings separately from codec |
| ARMv5TE CPU | developer_guide/02_00_hardware.md; see caveat below | A software 4K/24 real-time H.264 encoder is very unlikely |
| ISP / image preprocess | Canon DIGIC 5+ imaging functions; ML hardware guide | Need to identify whether the demosaic/color path can run at new width/height |
| EDMAC DMA | developer_guide/02_00_hardware.md and platform/5D3.123/consts.h (REG_EDMAC_WRITE_HD_ADDR, YUV422_HD_BUFFER_DMA_ADDR) | Hardware frame movement and pitch changes are possible research targets |
| Canon lossless JPEG | modules/silent/lossless.c, modules/raw_video/mlv_lite/mlv_lite.c | **Already operational** hardware-accelerated Bayer compression path |
| Canon H.264 recording | src/bitrate.c, src/mvr.h, platform/5D3.123/consts.h (MVR buffer and rate settings) | Codec exists, but exposed settings mostly control rate/quality rather than proven dimension changes |
| Picture Styles | src/picstyle.c | Good for 1080p tonality, **not** a solution for high-resolution encoding |

**CPU-count caveat:** a 2024 academic paper diagrams **two ARMv5TE CPUs in an EOS M DIGIC 5**; the ML hardware guide describes D4/5 as single-core from ML's main-CPU perspective. Neither establishes an exact 5D3 DIGIC 5+ physical CPU-core count. Do not claim a Mali/Adreno GPU or a specific CPU/core clock.

### Local source reconnaissance

- `platform/5D3.123/consts.h`: HD YUV422 buffer and EDMAC write destination symbols; some MVR buffer metrics; firmware-specific addresses.
- `src/bitrate.c`: H.264 bitrate, qscale, CBR/VBR controls; those are not image-size controls.
- `src/picstyle.c`: custom LUT-based .PF2 Picture Style and REC auto-selection; does not add a new encoder.
- `modules/silent/lossless.c`: calls Canon `ProcessTwoInTwoOutLosslessPath` and its related routines at 5D3 ROM addresses; uses EDMAC and JPCORE-like hardware.
- `modules/raw_video/mlv_lite/mlv_lite.c`: 14-bit and 12-bit lossless RAW compression modes; documents their constraints.
- `modules/crop_rec/crop_rec.c`: sensor timing/ENGIO hooks for experimental higher-resolution RAW readout.

## Storage math (uncompressed Bayer sensor data, decimal MB/s)

Formula: `width * height * fps * bits_per_pixel / 8 / 1,000,000`.
These are theoretical payload rates, **not measured** real bus throughput or recorded rates; exclude per-frame overhead.

| Geometry | 14-bit RAW | 12-bit RAW | 14-bit if lossless 1.8:1 |
|---|---:|---:|---:|
| 1920x1080 24 fps | 87.1 MB/s | 74.6 MB/s | 48.4 MB/s |
| 3072x1920 24 fps | 247.7 MB/s | 212.3 MB/s | 137.6 MB/s |
| 3840x1600 24 fps | 258.0 MB/s | 221.2 MB/s | 143.4 MB/s |
| 4096x1440 25 fps | 258.0 MB/s | 221.2 MB/s | 143.4 MB/s |
| 3840x2160 24 fps | 348.4 MB/s | 298.6 MB/s | 193.5 MB/s |

A constant 50 Mbit/s lossy bitstream writes just **6.25 MB/s**; at 100 Mbit/s it writes **12.5 MB/s**, irrespective of source image size. Real H.264 perceptual quality requires testing; encoder throughput (pixels/s), DRAM transactions and ISP bandwidth may still be the limit.

## Work plan / experiment gates

**Gate 0 — Read-only investigation (safe).** Locate 5D3 firmware version-specific tasks that configure H.264 input buffers, encoder dimension registers, stride, macroblock layout, tile geometry, reference frame buffers, encoded SPS and MOV metadata. Inspect ROM/QEMU traces and 5D3 platform register definitions. Record source commit SHA and firmware version.

**Gate 1 — Hardware capability map.** Instrument Canon's 1080p H.264 startup to capture encoder input channel/EDMAC width+pitch, source format (RGB/YUV), memory allocation and output stream's SPS. Compare to higher-resolution crop_rec sensor readout in the same firmware version. No register writes in this gate.

**Gate 2 — Minimal changes only after a convincing capability hypothesis.** Try noncritical controlled dimension changes; validate SPS cropping and actual image content (not just the MOV metadata), dropped frames, DMA consistency and memory allocation. Never jump straight to 4K. All camera tests carry crash/recovery plans. Firmware emulation cannot alone prove physical ISP/codec throughput.

**Gate 3 — LOG processing.** Determine where Canon's tone curve can be configured on a pipeline that actually supports the target resolution; choose a documented mathematical transfer function, test bit depth, clipping, gamma, quantization and 8-bit banding. If only 8-bit YUV420 H.264 is available, aggressively test post-grade stability.

**Gate 4 — Alternative compression.** If H.264 frame geometry is hardware-limited, benchmark Canon native lossless JPEG hardware and reduced-bit-depth Bayer compression, preserving demosaic/LOG for post. Consider compressed raw at 2.8K-3.2K as the realistic near-term fallback.

Success requires **real camera output demonstrating actual higher-resolution detail**, sustained recording, correct frame timestamps and reliable output—not merely a changed SPS/MOV header.

## Source evidence

1. Canon official 5D3 museum: https://global.canon/en/c-museum/product/dslr808.html
2. Canon 5D3 H.264 ALL-I/IPB press announcement: https://www.canon.ca/dam/about/News/Press-Releases/2012/2012-MAR-2-EOS5DMARKIII-EN.pdf
3. TechInsights DIGIC 5+ CH4-6501, Canon/TI: https://www.techinsights.com/products/far-1206-803
4. Magic Lantern hardware developer guide: https://github.com/reticulatedpines/magiclantern_simplified/blob/dev/developer_guide/02_00_hardware.md
5. Eberhart & Dietz (2024), *Magic Lantern as a Platform for Digital Photography Research*. **EOS M / DIGIC 5 example**, not exact 5D3 die: https://doi.org/10.2352/EI.2024.36.7.ISS-292
6. 2017 high-resolution experimental RAW modes: https://www.dpreview.com/news/8974010358/magic-lantern-brings-4k-recording-to-the-canon-eos-mark-iii/
7. Magic Lantern project: https://github.com/reticulatedpines/magiclantern_simplified

## Deployment safety

This document is research only. **No firmware binary or camera-ready patch has been validated.** Do not flash an experimental .FIR, adjust undocumented clocks or write undocumented H.264 registers on a valuable camera without reproducing the existing ROM state, recovery path and QEMU tests.
