// Dictionary word list: clip each row to its red bar and scroll the selected
// row when it is longer than the bar.
//
// Both list functions (0x66160 main game, 0x69F20 -Unlimited-) draw a row's
// name with `bl 0x39990` (text object, x, y, ..., colour s5-s7, alpha [sp]).
// Their coordinates are 960x540 units: a row is 39 high, the highlight bar is
// a 320-wide sprite centred 150 right of the row, and the text starts at the
// row's x (stock; the +4 that savelist_ips.py once added is no longer
// shipped). On screen the bar's ink ends 303 units past the text start, so a
// name may draw up to LIMIT before it is cut.
//
// The text drawer (0x126DA0) has its own marquee - style flag bit 4 at
// object+32 - but it only rotates the glyphs inside the text's own width and
// clips nothing, so a long name overflows exactly as much as before.
//
// State, after voicesub.s's 24 bytes in the slack past bss_end:
//   MQ+0   u64  text object of the row being drawn, or 0
//   MQ+8   f32  (unused)
//   MQ+12  f32  scroll offset for that row
//   MQ+16  u64  text object of the selected row
//   MQ+24  u32  frames since that row was selected

    .text

    .equ    LIMIT, 0x43970000           // 302.0
    .equ    HOLD, 0x42700000            // 60.0 frames before and after a scroll
    .equ    SPEED, 0x3f800000           // 1.0 unit a frame, as the drawer's own

// Hook at 0x663FC and 0x6A1A8, replacing `bl 0x39990`. Every argument
// register and [sp] are passed on untouched; only x9-x11 and s16-s19 are used.
// The selected row is the one drawn at full colour: s5 = 1.0, others 0.75.
    .global mq_draw
mq_draw:
    adrp    x9, MQ
    add     x9, x9, :lo12:MQ
    str     x0, [x9]
    str     wzr, [x9, #12]
    fmov    s16, #1.0
    fcmp    s5, s16
    b.ne    9f

    ldr     x10, [x9, #16]
    cmp     x10, x0
    b.eq    1f
    str     x0, [x9, #16]               // another row: start over
    str     wzr, [x9, #24]
1:  ldr     w10, [x9, #24]
    add     w11, w10, #1
    str     w11, [x9, #24]

    // Overflow = right edge of the laid-out text past LIMIT, both relative
    // to the text origin: max x is object+112 in glyph units, scale +120.
    ldr     s16, [x0, #112]
    ldr     s17, [x0, #120]
    fmul    s16, s16, s17
    mov     w11, #LIMIT
    fmov    s17, w11
    fsub    s16, s16, s17
    fcmp    s16, #0.0
    b.le    9f

    ucvtf   s17, w10
    mov     w11, #HOLD
    fmov    s18, w11
    fsub    s17, s17, s18               // frames into the scroll
    mov     w11, #SPEED
    fmov    s19, w11
    fmul    s17, s17, s19
    fmul    s18, s18, s19
    fadd    s18, s18, s16               // end of the hold after the scroll
    fcmp    s17, s18
    b.lt    2f
    str     wzr, [x9, #24]              // back to the start
    b       9f
2:  fmov    s18, wzr
    fmax    s17, s17, s18
    fmin    s17, s17, s16
    str     s17, [x9, #12]
9:  b       DRAW_TEXT

// Hook at 0x127134 in the drawer's glyph loop, replacing
// `cbz x20, 0x126F28` (x20 = transform). The quad is still in local units
// there: x0 [sp+88], x1 [sp+56], u0 [sp+176], u1 [sp+184], origin [sp+104].
// Only glyphs of the row mq_draw named are touched; a glyph wholly outside
// [origin, origin + LIMIT] is skipped the way the loop skips a missing one,
// and one across an edge is cut there with its u moved by the same fraction.
// Only caller-saved registers are used; the loop reloads all of them.
    .global mq_glyph
mq_glyph:
    adrp    x9, MQ
    add     x9, x9, :lo12:MQ
    ldr     x10, [x9]
    cmp     x10, x19
    b.ne    9f

    ldr     s16, [sp, #104]             // left edge
    mov     w11, #LIMIT
    fmov    s20, w11
    fadd    s20, s16, s20               // right edge
    ldr     s17, [x9, #12]
    ldr     s18, [sp, #88]
    ldr     s19, [sp, #56]
    fsub    s18, s18, s17
    fsub    s19, s19, s17
    fcmp    s19, s16
    b.le    8f
    fcmp    s18, s20
    b.ge    8f

    fsub    s23, s19, s18
    fcmp    s23, #0.0
    b.le    7f
    ldr     s21, [sp, #176]
    ldr     s22, [sp, #184]
    fsub    s24, s22, s21
    fdiv    s24, s24, s23               // u per unit
    fcmp    s18, s16
    b.ge    5f
    fsub    s25, s16, s18
    fmadd   s21, s25, s24, s21
    fmov    s18, s16
5:  fcmp    s19, s20
    b.le    6f
    fsub    s25, s19, s20
    fmsub   s22, s25, s24, s22
    fmov    s19, s20
6:  str     s21, [sp, #176]
    str     s22, [sp, #184]
7:  str     s18, [sp, #88]
    str     s19, [sp, #56]

9:  cbnz    x20, 1f
    b       GLYPH_FLAT
1:  b       GLYPH_MATRIX
8:  b       GLYPH_SKIP

// Hook at 0x63E2C and 0x67CD0, replacing the detail title's `bl 0x39990`.
// The title is centred on x = 650 (0x633FC, 0x6731C), which puts a long one
// over the vertical "Dictionary" at the bar's left end. Its laid-out edges
// (0x1274E0: object -> min, max, origin included) are kept inside
// [TITLE_L, TITLE_R] by moving x, and one wider than that is centred in it.
// A title that already fits is drawn where it always was.
    .equ    TITLE_L, 0x43e40000         // 456.0: 14 px past the label
    .equ    TITLE_R, 0x445e0000         // 888.0: 14 px inside the bar's end
    .global mq_title
mq_title:
    stp     x29, x30, [sp, #-80]!
    mov     x29, sp
    str     x0, [sp, #16]
    stp     s0, s1, [sp, #24]
    stp     s2, s3, [sp, #32]
    stp     s4, s5, [sp, #40]
    stp     s6, s7, [sp, #48]
    add     x1, sp, #56
    add     x2, sp, #64
    bl      TEXT_BOUNDS
    ldr     x0, [sp, #16]
    ldp     s0, s1, [sp, #24]
    ldp     s2, s3, [sp, #32]
    ldp     s4, s5, [sp, #40]
    ldp     s6, s7, [sp, #48]
    ldr     s16, [sp, #56]
    ldr     s17, [sp, #64]
    ldp     x29, x30, [sp], #80         // [sp] is the caller's alpha again

    fadd    s16, s16, s0                // left edge on screen
    fadd    s17, s17, s0                // right edge
    mov     w9, #TITLE_L
    fmov    s18, w9
    mov     w9, #TITLE_R
    fmov    s19, w9
    fsub    s20, s19, s18
    fsub    s21, s17, s16
    fcmp    s21, s20
    b.gt    2f
    fcmp    s16, s18
    b.ge    1f
    fsub    s20, s18, s16
    fadd    s0, s0, s20
    b       9f
1:  fcmp    s17, s19
    b.le    9f
    fsub    s20, s17, s19
    fsub    s0, s0, s20
    b       9f
2:  fadd    s20, s18, s19
    fadd    s21, s16, s17
    fsub    s20, s20, s21
    fmov    s21, #0.5
    fmadd   s0, s20, s21, s0
9:  b       DRAW_TEXT
