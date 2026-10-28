# How this fork was merged

This is a fork of [lucannez64/darling-lol](https://github.com/lucannez64/darling-lol) with a
second, independent set of Darling patches added on top — work done in parallel on the same
problem (running the macOS Riot/League client under Darling) without knowledge of that
project.

`patches/` is left **byte-identical to upstream** so `git pull upstream main` stays an
ordinary merge. Everything from this tree lives in `patches-jsabella/`, applied afterwards:

```sh
python3 scripts/prepare.py
python3 scripts/overlay.py          # --check-only to validate, --reverse to undo
```

## Why this was a merge and not a rebase

Every revision `upstream/manifest.json` pins is *exactly* the `HEAD` of the matching
repository in this tree, superproject included (`60ba801de`). All 32 components matched, so
the pinned revision is a genuine common ancestor and each component could be merged
three-way: pinned revision → {upstream's patch, this tree's working copy}.

## What went in

310 modified-or-new files from this tree were in scope. Deliberately excluded: the Riot
installer app and the game archive (not ours to redistribute, and upstream ships no game
files), one `.orig` patch backup, and the local progress log, which is full of absolute
paths.

| | files |
|---|---|
| merged with no conflict | 193 |
| combined mechanically (both sides only *added* at the same point) | 41 |
| contested — 243 conflict regions in all | 76 |

The contested set was lopsided in a way that decided the policy. 132 of the 243 regions were
in the rendering and font stack — CoreText (69), QuartzCore (25), IOSurface/OpenGL (17), the
X11 backend (12), CoreVideo (9). That is the code upstream's tree plays at ~130 FPS with, and
the same code that was still painting black in this tree. The other 111 regions were the
syscall and plumbing layer, where this tree has fixes upstream lacks.

**Policy: upstream wins the rendering/font/compositing stack; this tree wins the
syscall/plumbing layer.** Applied per conflict *region*, not per file, so a contested file
keeps everything that merged cleanly and only the contested regions go to the winner.

## Decided individually

Where neither label fit, or where the mechanical rule would have been wrong:

| file | kept | why |
|---|---|---|
| `Carbon/HIToolbox/.../Events.cpp` | this tree | `LMGetKbdLast` is an ADB address (macOS answers 2); upstream returned `LMGetKbdType()`, a different quantity |
| `corefoundation/NSArray.m`, `NSDictionary.m` | this tree | `-writeToURL:error:` surfaces the real `CFError` instead of a synthesized `NSFileWriteUnknownError` |
| `xnu/.../network/accept.c` | this tree | both added the NULL-peer guard, but this one routes through the shared fixup so `PF_LOCAL` paths are mapped out of the prefix |
| `cocotron/.../NSAccessibilityRemoteUIElement.{h,m}` | this tree, **plus** upstream's `-init` | this implementation has the real token struct, correct types, `dealloc` and `processIdentifier`; upstream's `-init` is load-bearing — without it `init` falls through to `-forwardInvocation:`, whose `"v@:"` signature returns a garbage pointer, which is the Chromium crash they documented |
| `Libinfo/darling-resolver/resolver.c` | upstream | they replaced `res_query` with their own `dr_query` host-DNS path that has tests behind it; this tree's thread-safe `res_nquery` rewrite would have deleted that feature |
| `xnu/.../bsdthread_register.c` | upstream | part of their measured process-local mutex work |
| `xnu/.../signal/sigexc.c` | upstream | both replaced `kill(0, sig)` with `tgkill(pid, tid, sig)`; identical in effect |
| `src/sandbox/sandbox.c` | upstream | their `operation == NULL` probe is documented against Chromium's `Seatbelt::IsSandboxed()` CHECK; this tree's `sandbox_applied` flag would have been dead code beside it |
| `src/startup/mldr/elfcalls/elfcalls.c` | upstream | both independently set `calls->exit = _exit`; identical change, different rationale |
| `CoreMedia/.../CMFormatDescription.h` | upstream | strict superset of this tree's version, plus `extern "C"` guards |
| `cocotron/AppKit/nib.subproj/NSNib.m` | upstream | both wrote the identical `-instantiateWithOwner:topLevelObjects:` forwarder |
| `libnotify/notifyd/CMakeLists.txt` | upstream | they install the launchd job, which is why `notify_register_*` stops returning `NOTIFY_STATUS_SERVER_NOT_FOUND` |

## Two hazards found and fixed

**106 duplicate method definitions.** Both trees filled the same Cocotron gaps for the same
Electron client, so each added its own `-masksToBounds`, `-titleVisibility`,
`-copyFamilyName` and so on. Added at *different points* in a file, those merge as text with
no conflict at all and leave the method defined twice, which does not compile — so this
affected cleanly-merged files too, not just resolved ones. Each duplicate was removed
surgically, by definition, keeping the subsystem owner's copy, so unrelated work in the same
file survived (e.g. the `-[NSView _setWindow:]` drawable fix, which is still here).

**6 files left with unbalanced braces** by per-region resolution, where one side's region
opened a brace the other side's closed. Those took the subsystem winner's whole file:
`iokitd/src/ServiceRegistry.mm`, `cocotron/CoreText/CTFont.m`,
`cocotron/QuartzCore/CARenderer.m`, `IOSurface/include/IOSurface/IOSurfacePriv.h` to
upstream; `CoreAudio/HostTime.mm`, `darlingserver/duct-tape/src/memory.c` to this tree. The
other side's clean additions to those six files are the one real loss in this merge.

`CoreServices/reexport.exp` is kept at upstream's bytes: this tree's only change to it was an
accidental CRLF→LF conversion.

## Fixes this tree contributes that upstream does not have

- **`darlingserver` `MessageQueue::sendMany` tolerates `ENOTCONN`.** Upstream hit the same
  crash class and added `ENOENT`; the socket is an unconnected `SOCK_DGRAM` listener and the
  send loop nulls `msg_name` for an all-NUL `sun_path`, so the kernel answers `ENOTCONN`. The
  main loop has no try/catch, so one addressless message killed the whole prefix.
- **`iokitd` IOSurface retain invariant.** `incrementSurfaceUseCount()` created the tracking
  entry without the retain it stands for, and `lookupById()` retained on every lookup while
  tracking is idempotent. Both now go through `trackSurfaceForCaller()`, which reports
  whether it created the entry and ties the retain to it.
- **`-[NSView _setWindow:]` no longer destroys live CGL drawables** — upstream patched
  `-_createLayerContextIfNeeded`, which already had the `if (_window)` guard, and left
  `_setWindow:` unguarded.
- The 57-file `security` / certificate stack, which merged with no conflict at all.

## What is verified, and what is not

Verified mechanically, all green:

- every pinned revision equals this tree's `HEAD` for that component (32/32)
- no conflict markers anywhere
- no method defined more times than either input side defined it (differential, so several
  `@implementation` blocks per file and overloaded selector families are not false positives)
- no file whose brace balance the merge changed
- each of the 16 overlay patches re-applies to upstream's patched tree and reproduces the
  merged tree **byte for byte** (`git write-tree` equality)

**Not verified: this has not been compiled, installed or run.** A full Darling build was out
of scope here. Treat `scripts/overlay.py --check-only` passing as "the patches apply", not as
"it builds". Expect compile errors in the mixed files first.

## Regenerating the overlay against a newer upstream

The overlay is `diff(upstream's patched tree → merged tree)` per component. After pulling
upstream, re-merge the same way: clone each component at its pinned revision, apply
`patches/<c>.patch` on one branch and this tree's files on another, merge, re-resolve, then
re-emit each `patches-jsabella/<c>.patch`. Generate the diffs as **bytes** — capturing them
as text applies universal-newline translation and silently strips the CRs out of any CRLF
file's context lines, after which the patch no longer applies.
