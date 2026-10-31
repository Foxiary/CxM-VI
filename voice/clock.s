// The clock card at chapter starts (ADV/EFFECT/310.CL3, texture 現在時刻):
// put AM/PM after the minutes, as the English -Unlimited- does.
//
// The card's CWD draws its cells left to right: 月10 月1 | 日10 日1 |
// AM/PM 時10 時1 : 分10 分1. The English -Unlimited- keeps that CWD (its
// CWDL002 file has the same objects at the same places) and moves the time
// cells in code instead: in the sprite loop of the CWD player (EN 0x11F580),
// after the four corners of a quad are laid out on the stack and before it is
// sent (EN 0x11FB04..0x11FC48), it memcmps the texture's name with "現在時刻"
// and, if it matches, shifts all four corner x by an amount set by the first
// corner's x (960x540 units):
//     x < 200          unchanged   (MONTH, DAY, the band)
//     200 <= x < 500   +15
//     500 <= x < 600   +135        (AM/PM moves past the minutes)
//     600 <= x         -54         (hours, colon, minutes move left)
// The JP player (0x110F70) is the same function without that block, so this
// adds it at the matching point: the hook replaces `bl 0x106BA0` at 0x111484,
// the first call after the quad is complete (EN 0x11FC50, same callee), and
// tail-calls it with w0/w1 untouched.
//
// At the hook (JP frame): x28 = the CWD texture object, its name at
// x28 + 24 + 32 (EN reads it there through 0x118B80); the four corners are
// float pairs at sp+88, sp+128, sp+168, sp+208 (EN sp+392, +432, +472, +512);
// x0-x18 are free, and w0/w1 must reach 0x106BA0 as they were.

    .text

    .global ck_draw
ck_draw:
    stp     x29, x30, [sp, #-48]!
    mov     x29, sp
    stp     x0, x1, [sp, #16]
    stp     x2, x3, [sp, #32]

    add     x0, x28, #56                // name
    adrp    x1, ck_name
    add     x1, x1, :lo12:ck_name
    mov     x2, #9
    bl      MEMCMP
    cbnz    w0, 9f

    add     x9, sp, #48                 // the caller's sp
    ldr     s0, [x9, #88]
    mov     w10, #0x43480000            // 200.0
    fmov    s1, w10
    fcmp    s0, s1
    b.mi    9f
    mov     w10, #0x43fa0000            // 500.0
    fmov    s1, w10
    mov     w11, #0x41700000            // +15.0
    fcmp    s0, s1
    b.mi    1f
    mov     w10, #0x44160000            // 600.0
    fmov    s1, w10
    mov     w11, #0x43070000            // +135.0
    fcmp    s0, s1
    b.mi    1f
    mov     w11, #0xc2580000            // -54.0
1:  fmov    s2, w11
    ldr     s1, [x9, #88]
    fadd    s1, s1, s2
    str     s1, [x9, #88]
    ldr     s1, [x9, #128]
    fadd    s1, s1, s2
    str     s1, [x9, #128]
    ldr     s1, [x9, #168]
    fadd    s1, s1, s2
    str     s1, [x9, #168]
    ldr     s1, [x9, #208]
    fadd    s1, s1, s2
    str     s1, [x9, #208]

9:  ldp     x0, x1, [sp, #16]
    ldp     x2, x3, [sp, #32]
    ldp     x29, x30, [sp], #48
    b       CK_SEND

    .section .rodata
ck_name:
    .byte   0x8c, 0xbb, 0x8d, 0xdd, 0x8e, 0x9e, 0x8d, 0x8f, 0   // 現在時刻 (Shift-JIS)
