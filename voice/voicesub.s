// English voice-recorder subtitles for the JP build of Collar×Malice.
//
// The JP executable has two voice recorders. The main game's (handlers at
// 0xC50B0/0xC55E0, draw 0xC5160) is the one the English build extends; the
// one at 0xC7A00/0xC8CC0 (character tabs, 17 portraits) is -Unlimited-'s.
// Hooking the second one shows nothing in the main game, so every hook here
// is in the first. Its struct matches the English one less the subtitle
// slot: playing flag at +272 (EN +280), list position at +84/+88 (EN +92/+96).
//
// Linked at the end of .text (0x2729F0), inside the page padding before
// .rodata at 0x273000, so no segment moves. Every address below is reached
// PC-relative: the module loads at a random base, so a movz/movk of a
// link-time address points at nothing.
//
// State lives past MOD0's bss_end (0x157B3D8) and before the end of the
// module's last page (0x157C000): zero-filled by the loader, referenced by
// no code and no relocation.
//
//   G+0   u64  subtitle texture, or 0
//   G+8   u32  clip id the texture was loaded for
//   G+12  u32  clip id the player last started
//   G+16  u64  voice-recorder UI of the frame being drawn

    .text

// Hook at 0xC4258, replacing `strb w8, [x19, #272]` where playback starts.
// The clip id is the list position, as in the English build. x9/x10 are dead
// here; everything else is left alone.
    .global vs_play
vs_play:
    strb    w8, [x19, #272]
    ldp     w9, w10, [x19, #84]
    add     w9, w9, w10
    adrp    x10, G
    add     x10, x10, :lo12:G
    str     w9, [x10, #12]
    ret

// Hook at 0xC52F0, replacing `ldr x19, [x19, #16]`: the draw function
// overwrites its UI pointer there, so keep a copy for vs_tail.
    .global vs_save
vs_save:
    adrp    x9, G
    add     x9, x9, :lo12:G
    str     x19, [x9, #16]
    ldr     x19, [x19, #16]
    ret

// Hook at 0xC5408, replacing the draw function's tail call `b 0xE0B70`.
// Reached by `b`, so x30 is the draw function's caller. Makes that last
// draw, then draws the subtitle above everything, as the English build does.
// s7 carries the screen alpha into the tail call.
    .global vs_tail
vs_tail:
    sub     sp, sp, #0x150
    stp     x29, x30, [sp, #0x120]
    stp     x20, x21, [sp, #0x130]
    stp     x19, xzr, [sp, #0x140]
    str     d8, [sp, #0x148]
    add     x29, sp, #0x120
    fmov    s8, s7
    bl      TEX_SUBDRAW

    adrp    x21, G
    add     x21, x21, :lo12:G
    ldr     x19, [x21, #16]
    cbz     x19, .Lout

    ldrb    w8, [x19, #272]             // playing
    cbz     w8, .Lfree
    ldr     w20, [x21, #12]
    cmp     w20, #24                    // 25 subtitles, 00..24
    b.hi    .Lfree

    // Only the main game ships these files (archive 3, GAME_01). The disc
    // index is worked out exactly as the JP loader does at 0xC596C.
    adrp    x8, DISC_GOT
    ldr     x8, [x8, :lo12:DISC_GOT]
    ldr     w8, [x8]
    cmp     w8, #2
    b.lo    1f
    add     w9, w8, #2
    add     w10, w8, #3
    cmp     w9, #0
    csel    w10, w10, w9, lt
    and     w10, w10, #0xfffffffe
    sub     w8, w9, w10
1:  cbnz    w8, .Lfree

    fcmp    s8, #0.0
    b.le    .Lout

    ldr     x0, [x21]
    cbz     x0, .Lload
    ldr     w9, [x21, #8]
    cmp     w9, w20
    b.eq    .Ldraw
    str     xzr, [x21]                  // another clip started
    bl      TEX_FREE

.Lload:
    mov     x0, sp
    mov     w1, #0x100
    adr     x2, fmt
    mov     w3, w20
    bl      SNPRINTF
    mov     w0, #3
    mov     x1, sp
    mov     x2, xzr
    mov     w3, #2
    mov     w4, wzr
    mov     w5, #1
    mov     w6, wzr
    bl      TEX_LOAD
    str     x0, [x21]
    str     w20, [x21, #8]
    cbz     x0, .Lout

.Ldraw:
    ldr     x0, [x21]
    ldrb    w9, [x0, #139]              // loaded
    cbz     w9, .Lout
    ldr     x9, [x0, #32]
    cbz     x9, .Lout
    mov     w9, #0x43900000             // 288.0
    fmov    s0, w9
    mov     w9, #0x42b00000             // 88.0
    fmov    s1, w9
    fmov    s2, wzr
    fmov    s3, s8
    bl      TEX_DRAW
    b       .Lout

.Lfree:
    ldr     x0, [x21]
    cbz     x0, .Lout
    str     xzr, [x21]
    bl      TEX_FREE

.Lout:
    ldr     d8, [sp, #0x148]
    ldr     x19, [sp, #0x140]
    ldp     x20, x21, [sp, #0x130]
    ldp     x29, x30, [sp, #0x120]
    add     sp, sp, #0x150
    ret

// Hook at 0xC55A4 in the teardown 0xC5550, replacing `ldr x0, [x19, #280]`.
// Releases a subtitle still held when the screen closes.
    .global vs_release
vs_release:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    adrp    x9, G
    add     x9, x9, :lo12:G
    str     xzr, [x9, #16]
    ldr     x0, [x9]
    cbz     x0, 1f
    str     xzr, [x9]
    bl      TEX_FREE
1:  ldr     x0, [x19, #280]
    ldp     x29, x30, [sp], #16
    ret

fmt:
    .asciz  "/VOICERECORDER/SUBTITLE/%02u.tid"
    .balign 4
