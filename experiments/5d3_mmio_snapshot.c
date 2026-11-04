/*
 * EOS 5D Mark III DIGIC 5+ / CH4-6501: direct, read-only EDMAC register snapshot.
 *
 * RESEARCH SAMPLE ONLY. Not wired into a camera task, interrupt, or build.
 * Does not call any Canon ROM function, Magic Lantern API, or a GPU driver.
 * NOT an encoder driver and NOT evidence of >1080p H.264 capability.
 *
 * Address meanings are taken from:
 *   platform/5D3.113/consts.h
 *   platform/5D3.123/consts.h
 *   src/edmac.c
 *
 * Future on-camera evaluation requires firmware/version and timing checks.
 * Unknown registers, and JPCORE registers at 0xC0E20000, are intentionally
 * NOT read: some device registers have read-side effects.
 */

#include <stdint.h>

#define REG_EDMAC_WRITE_HD_BASE  (0xC0F04A00u)
#define REG_EDMAC_WRITE_LV_BASE  (0xC0F04500u)

struct d5_edmac_snapshot
{
    uint32_t hd_status;       /* base + 0x00 */
    uint32_t hd_flags;        /* base + 0x04 */
    uint32_t hd_address;      /* base + 0x08: YUV HD buffer */
    uint32_t hd_length;       /* base + 0x10: transfer dimensions */
    uint32_t lv_address;      /* base + 0x08: LiveView buffer */
};

/* CPU does a raw volatile ARM load on the memory-mapped IO bus. */
static inline uint32_t digic_read32(uint32_t address)
{
    return *(volatile const uint32_t *)(uintptr_t)address;
}

/* Read-only; callers must ensure that these MMIO locations are safe to sample. */
void d5_snapshot_video_edmac(struct d5_edmac_snapshot *out)
{
    if (!out) return;
    out->hd_status  = digic_read32(REG_EDMAC_WRITE_HD_BASE + 0x00u);
    out->hd_flags   = digic_read32(REG_EDMAC_WRITE_HD_BASE + 0x04u);
    out->hd_address = digic_read32(REG_EDMAC_WRITE_HD_BASE + 0x08u);
    out->hd_length  = digic_read32(REG_EDMAC_WRITE_HD_BASE + 0x10u);
    out->lv_address = digic_read32(REG_EDMAC_WRITE_LV_BASE + 0x08u);
}
