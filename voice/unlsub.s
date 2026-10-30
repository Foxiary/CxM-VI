// English subtitles for -Unlimited- in the JP build: the voice recorder, and
// the character's line on the Extra screen (below).
//
// The -Unlimited- recorder (state machine 0xC636C, draw 0xC7AB0, teardown
// 0xC7FC0) plays a clip at 0xC6888 and keeps a playing flag at +520, which
// the list state (3, state word at +584) clears once the voice stops. The
// English build shows a panel with the question and a scrollable answer for
// as long as the clip plays; unlsub.py renders that panel, one texture per
// row of dbLibVoiceRecorder_02, as GAME_02 VOICERECORDER/SUBTITLE/%02u.tid.
//
// Coordinates are the engine's 960x540 units; the textures hold 2 texels per
// unit, which is what TEX_QUAD expects (it halves the texture size).
//
//   US+0   u64  texture, or 0
//   US+16  u32  row the texture was loaded for
//   US+20  u32  row of the clip playing, or -1
//   US+24  u32  first line shown
//   US+28  u32  lines - 16, 0 until the texture is in

    .text

// Hook at 0xC6888, replacing `bl 0x14D90`, which plays voice w0. w20 is the
// database row of the clip, or -1.
    .global us_play
us_play:
    adrp    x9, US
    add     x9, x9, :lo12:US
    str     w20, [x9, #20]
    stp     wzr, wzr, [x9, #24]
    b       PLAY_VOICE

// Hook at 0xC652C, replacing `bl 0xC6D50`, the list's cursor input (x0 the
// recorder). While a subtitle is up, up and down scroll it instead, as in the
// English build, and the list stays where it is.
    .global us_nav
us_nav:
    adrp    x9, US
    add     x9, x9, :lo12:US
    ldr     w10, [x9, #20]
    tbnz    w10, #31, 1f
    ldrb    w10, [x0, #520]
    cbz     w10, 1f
    strb    wzr, [x0, #576]             // what 0xC6D50 clears first
    adrp    x10, PAD_GOT
    ldr     x10, [x10, :lo12:PAD_GOT]
    ldr     x10, [x10]                  // pad 0, as 0x169740 returns it
    ldr     w10, [x10, #32]             // repeat mask
    ldp     w11, w12, [x9, #24]
    ubfx    w13, w10, #22, #1           // 0x400000 down
    add     w11, w11, w13
    ubfx    w13, w10, #20, #1           // 0x100000 up
    sub     w11, w11, w13
    cmp     w11, w12
    csel    w11, w12, w11, gt
    bic     w11, w11, w11, asr #31
    str     w11, [x9, #24]
    ret
1:  b       LIST_NAV

// Hook at 0xC7FEC in the teardown, replacing `ldr x0, [x19, #8]`.
    .global us_release
us_release:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    bl      us_free
    ldr     x0, [x19, #8]
    ldp     x29, x30, [sp], #16
    ret

// Forget the clip and drop its texture.
us_free:
    adrp    x9, US
    add     x9, x9, :lo12:US
    mov     w10, #-1
    str     w10, [x9, #20]
    ldr     x0, [x9]
    cbz     x0, 1f
    str     xzr, [x9]
    b       TEX_FREE
1:  ret

// Hook at 0xC7A3C, replacing `bl 0xC7AB0`, the recorder's draw (x0 the
// recorder, s0 its alpha). The subtitle goes on top, under the fade that
// 0xC7A00 draws next.
    .global us_draw
us_draw:
    sub     sp, sp, #0x130
    stp     x29, x30, [sp, #0x100]
    stp     x19, x20, [sp, #0x110]
    stp     x21, x22, [sp, #0x120]
    add     x29, sp, #0x100
    mov     x19, x0
    bl      DRAW_UREC

    adrp    x20, US
    add     x20, x20, :lo12:US
    ldr     w8, [x19, #584]
    cmp     w8, #3                      // the list, where clips play
    b.ne    .Loff
    ldrb    w8, [x19, #520]
    cbz     w8, .Loff
    ldr     w21, [x20, #20]
    tbnz    w21, #31, .Loff

    ldr     x0, [x20]
    cbz     x0, .Lload
    ldr     w8, [x20, #16]
    cmp     w8, w21
    b.eq    .Lready
    str     xzr, [x20]
    bl      TEX_FREE
.Lload:
    mov     x0, sp
    mov     w1, #0x100
    adr     x2, us_fmt
    mov     w3, w21
    bl      SNPRINTF
    mov     w0, #4                      // GAME_02
    mov     x1, sp
    mov     x2, xzr
    mov     w3, #2
    mov     w4, wzr
    mov     w5, #1
    mov     w6, wzr
    bl      TEX_LOAD
    str     x0, [x20]
    str     w21, [x20, #16]

.Lready:
    ldr     x21, [x20]
    cbz     x21, .Lout
    ldrb    w8, [x21, #139]             // loaded
    cbz     w8, .Lout
    ldr     x8, [x21, #32]
    cbz     x8, .Lout
    ldr     w8, [x20, #16]
    adr     x9, us_lines
    ldrb    w22, [x9, x8]               // lines
    subs    w8, w22, #16
    csel    w8, w8, wzr, gt
    str     w8, [x20, #28]

    mov     x0, x21                     // panel, question, track
    adr     x8, us_panel
    bl      us_rec

    adr     x8, us_body                 // 16 lines from US+24
    ldp     s0, s1, [x8]
    ldp     s3, s4, [x8, #8]
    ldp     s5, s6, [x8, #16]           // s6: one line
    ldr     s16, [x20, #24]
    scvtf   s16, s16
    fmadd   s4, s16, s6, s4
    mov     w8, #16
    cmp     w22, w8
    csel    w8, w22, w8, lt
    scvtf   s16, w8
    fmul    s6, s6, s16
    mov     x0, x21
    bl      us_quad

    ldr     w8, [x20, #28]              // thumb, when it scrolls
    cbz     w8, .Lout
    adr     x9, us_thumb
    ldr     s16, [x20, #24]
    scvtf   s16, s16
    scvtf   s17, w8
    fdiv    s16, s16, s17
    ldr     s17, [x9, #24]              // travel
    ldp     s0, s1, [x9]
    fmadd   s1, s16, s17, s1
    ldp     s3, s4, [x9, #8]
    ldp     s5, s6, [x9, #16]
    mov     x0, x21
    bl      us_quad

.Lout:
    ldp     x21, x22, [sp, #0x120]
    ldp     x19, x20, [sp, #0x110]
    ldp     x29, x30, [sp, #0x100]
    add     sp, sp, #0x130
    ret
.Loff:
    bl      us_free
    b       .Lout

// --- The Extra screen ------------------------------------------------------
//
// The -Unlimited- character menu (ALBUM / VOICE RECORDER / ...; state machine
// 0xC15C0, draw handler 0xC3240) has a character greet you through three
// calls to PLAY_VOICE. The English build shows the line in a message box for
// as long as the voice plays; unlsub.py renders box and line together as
// SUBTITLE/<voice id>.tid.
//
//   UR+0   u64  texture, or 0
//   UR+8   u32  voice id the texture was loaded for
//   UR+12  u32  voice id of the line playing, or 0

// Hooks at 0xC162C, 0xC1758 and 0xC19F8, each replacing `bl 0x14D90`.
    .global ur_play
ur_play:
    adrp    x9, UR
    add     x9, x9, :lo12:UR
    str     w0, [x9, #12]
    b       PLAY_VOICE

// Hook at 0xC22A4, the screen's teardown, replacing `bl 0x107D60` (freeing
// its extra_charParts).
    .global ur_release
ur_release:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    bl      TEX_FREE
    bl      ur_free
    ldp     x29, x30, [sp], #16
    ret

ur_free:
    adrp    x9, UR
    add     x9, x9, :lo12:UR
    str     wzr, [x9, #12]
    ldr     x0, [x9]
    cbz     x0, 1f
    str     xzr, [x9]
    b       TEX_FREE
1:  ret

// Hook at 0xC3298, replacing `bl 0xC2CC0`, the last thing the draw handler
// draws (x0 the screen). The English build draws its box right there too.
    .global ur_draw
ur_draw:
    sub     sp, sp, #0x120
    stp     x29, x30, [sp, #0x100]
    stp     x19, x20, [sp, #0x110]
    add     x29, sp, #0x100
    bl      DRAW_XPARTS
    adrp    x20, UR
    add     x20, x20, :lo12:UR
    ldr     w19, [x20, #12]
    cbz     w19, 9f
    bl      IS_PLAYING
    tbz     w0, #0, 8f

    ldr     x0, [x20]
    cbz     x0, 1f
    ldr     w8, [x20, #8]
    cmp     w8, w19
    b.eq    2f
    str     xzr, [x20]
    bl      TEX_FREE
1:  mov     x0, sp
    mov     w1, #0x100
    adr     x2, us_fmt
    mov     w3, w19
    bl      SNPRINTF
    mov     w0, #4                      // GAME_02
    mov     x1, sp
    mov     x2, xzr
    mov     w3, #2
    mov     w4, wzr
    mov     w5, #1
    mov     w6, wzr
    bl      TEX_LOAD
    str     x0, [x20]
    str     w19, [x20, #8]

2:  ldr     x0, [x20]
    cbz     x0, 9f
    ldrb    w8, [x0, #139]              // loaded
    cbz     w8, 9f
    ldr     x8, [x0, #32]
    cbz     x8, 9f
    adr     x8, ur_box
    bl      us_rec
9:  ldp     x19, x20, [sp, #0x110]
    ldp     x29, x30, [sp, #0x100]
    add     sp, sp, #0x120
    ret
8:  bl      ur_free                     // the voice has stopped
    b       9b

// x0 texture, x8 -> {x, y, u, v, w, h}.
us_rec:
    ldp     s0, s1, [x8]
    ldp     s3, s4, [x8, #8]
    ldp     s5, s6, [x8, #16]
// x0 texture, (s0, s1) on screen, (s3, s4) in the texture, (s5, s6) the size
// in both. TEX_QUAD takes z in s2 and the colour in s7, [sp], [sp, #8],
// [sp, #16].
us_quad:
    sub     sp, sp, #48
    stp     x29, x30, [sp, #32]
    add     x29, sp, #32
    fmov    s7, #1.0
    str     s7, [sp]
    str     s7, [sp, #8]
    str     s7, [sp, #16]
    fmov    s2, wzr
    bl      TEX_QUAD
    ldp     x29, x30, [sp, #32]
    add     sp, sp, #48
    ret

// voicesub.py places this section in the page padding after .rodata, within
// adr range of the code.
    .section .rodata
    .balign 4
// {x, y, u, v, w, h} in units. The panel is the English one at (125, 75).
us_panel:   .float 125.0, 75.0, 0.0, 0.0, 791.0, 447.0
// The answer: ink of its first line at y 148.3 as in the English build; h is
// one line, 44 texels.
us_body:    .float 265.0, 147.5, 0.0, 454.5, 632.0, 22.0
// The thumb, then how far it travels down the track.
us_thumb:   .float 879.0, 151.5, 772.0, 450.0, 16.0, 63.0, 266.5
// The Extra screen's box, where the English build draws it.
ur_box:     .float 350.0, 400.0, 0.0, 0.0, 610.0, 132.0
us_fmt:
    .asciz  "/VOICERECORDER/SUBTITLE/%02u.tid"
// Lines in each row's answer; unlsub.py tex checks this against the text.
us_lines:
    .byte   31, 29, 28, 33, 29, 25, 22, 22, 31, 40, 23, 30, 27, 25, 29, 21
    .byte   23, 21, 26, 41, 24, 30, 21, 39, 35, 32, 36, 26, 27, 31, 36, 27
    .byte   23, 25, 38, 25, 22, 26, 25, 28, 35, 28, 30, 33, 34, 36, 41, 25
    .byte   35, 29, 13, 15, 13, 14, 19, 12, 9, 16, 16, 11, 11, 12, 12, 13
    .byte   14, 10, 11, 12, 11, 17, 10, 14, 13, 14, 14, 14, 14, 18, 17, 13
    .byte   11, 14, 15
    .balign 4
