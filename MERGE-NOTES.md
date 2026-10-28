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

## How the contested files were resolved

117 files were contested. The policy changed twice, each time because a real build found
something no textual merge or symbol audit could see, and the final shape is:

**Implementations: whole file, from one side.** Per-*region* resolution was tried first and
is wrong. Where both sides rewrote the body of one function while leaving its signature as
context, git merges the two bodies as adjacent text with no conflict at all: `removexattr.c`
came out calling `vchroot_expand` twice and issuing the removexattr syscall twice, mixing one
side's error mapping with the other's. No symbol-level check can see that, because the symbol
is defined exactly once. So a contested implementation file is taken entire from whichever
side owns that subsystem: 67 files from darling-lol, 50 from this tree.

**Headers: the union of both sides.** A header is a list of declarations, not logic, and both
sides only ever appended to it. Picking a side there discards the other side's declarations
while its implementation — which merged cleanly, as a union of both sides' code — still uses
them, and the build fails with `use of undeclared identifier` a long way from the header. 14
contested headers are therefore re-merged three-way with `git merge-file --union`, gated on
*neither* side having deleted a line, so nothing can be lost that way. One (`NSSpeechSynthesizer.h`)
produced a structurally invalid file — a second `@interface` with no matching `@end` — and is
rejected by a scope/conditional balance check and falls back to a whole-file choice.

**Features, not files, decide the unit.** Whole-file resolution picks each file alone, so it
will take a header from one side and its implementation from the other. Where both sides
built the *same* feature the halves then disagree about types, struct members, selectors, or
— worst, because it survives compilation — about which functions exist at all. These groups
are forced to one side as a unit:

| group | side | why |
|---|---|---|
| all of `iokitd` (32 files) | darling-lol | Both sides implemented IOKit interest notifications independently — this tree as `IOInterestNotification.cpp`, theirs as `.mm`, each with its own header — and the merge kept both files *and* both CMake entries. Theirs is the complete one (286 lines against 41, with retry, port liveness and message flushing). Their `IOObject`/`IOService` changes subsume this tree's: their `~IOObject` cancels the dispatch source with a handler capturing only the port, and their `is_io_service_open_extended` deallocates the properties memory and task right that this tree's leaks. |
| `src/frameworks/IOSurface` | darling-lol | Must match the iokitd server: the two sides' wire structs differ (theirs has no `allocSize`), and theirs is the API-faithful Mach-port path (`IOSurfaceCreateMachPort`, `IOSurfaceLookupFromMachPort`) that multi-process Chromium uses. This tree's file-backed route was unfinished. |
| darlingserver `message.{hpp,cpp}`, `call.cpp`, `fileport.c`, `duct-tape.h` | darling-lol | `message.hpp` declares `initializeServerCredentials()` and `pushAndSend()`, which only their `message.cpp` defines and their `darlingserver.cpp`/`server.cpp` call — the server did not link otherwise. Their fileport scopes the port to the process's dtape task, which is what multi-process Chromium needs. |
| cocotron `CGDirectDisplay.{h,m}` | darling-lol | Theirs rewrote the implementation (120+/38-); this tree's additions conflict with their prototypes for `CGDisplayIsBuiltin`/`CGDisplayUsesForceToGray`. |
| cocotron `CoreText/*` (bar its `CMakeLists.txt`) | this tree | One tightly coupled subsystem — `CTFont`, `KTFont` and `CTFontDescriptor` share internal structs and private functions — that resolution had split, leaving this tree's `CTFontManager.m` calling a `CTFontDescriptorCreateWithNameAndSize` that only its own files declare and define. This tree is much the larger side (~1140 added lines against ~600). Their `CMakeLists.txt` stays: both sides made the same source-list change and theirs additionally links fontconfig. |
| cocotron `Onyx2D/O2Font*`, `CoreGraphics/CGFont.*` | this tree | The font stack reaches past CoreText: `O2FontCopyFaceList`, the `O2FontFace*` keys and `CGFontCopyTableTags` exist only on this side, so CoreText linked against nothing. 342 lines against 51 in `O2Font_freetype.m`, 144 against 17 in `O2Font.m`. |
| cocotron `NSResponder.{h,m}` | this tree | Both added touch-bar support with different types — typed `NSTouchBar *` plus `makeTouchBar` here, `id`-based there. A genuine conflict, so the header could not be unioned and fell back to theirs, leaving the merged `.m` calling `makeTouchBar` with `NSTouchBar` undeclared. Their three `otherMouse*` declarations are grafted back, since their `.m` defines them. |
| cocotron `CATransactionGroup`, `CGContext`, `CTFontManager`, `NSScreen` (h+m) | this tree | In each the header is this tree's alone and declares what its implementation defines, but the `.m` had gone the other way. |
| root `TextInputSources.{h,mm}`, `TextServices.{h,c}` | this tree | They never touched `TextServices.h`, so resolving it to "theirs" meant resolving it to the pinned revision and dropping this tree's TSM declarations while keeping its definitions of them. |

## Grafts and hand-decisions

Six edits that no rule produces, each recorded in the pipeline with its reason:

- **`notifyCheckin`** takes a second argument here (the checking-in thread's nsid): every
  thread checks in, and only the main thread's checkin means the process has arrived, so only
  that one may wake a parent in `fork_wait_for_child`. `call.cpp` is darling-lol's, so the
  extra argument is grafted onto their call site. Both sides independently fixed the same
  null-semaphore crash in `notifyCheckin`; this tree's version also distinguishes the main
  thread, so its `process.cpp` is kept.
- **`sendMany`'s undeliverable-message test** was widened by both sides to different errnos —
  `ECONNRESET`/`ENOTCONN` here (an addressless datagram on an unconnected socket, which used
  to terminate the whole server and with it every process in the prefix), `ENOENT` there. The
  union is correct; every one of them means the message can never be delivered.
- **`CoreServices` re-export generation.** This tree appends the `NSUserActivity` class
  symbols to the list it reads from `reexport.exp`, whose last line has no trailing newline —
  so the first appended symbol was concatenated onto it and the link failed on
  `_remquo$fenv_access_off_OBJC_CLASS_$_NSUserActivity`, a symbol that is really two. It also
  wrote and passed the 32-bit list unconditionally, and darling-lol configures with
  `TARGET_i386=OFF`, so ld was handed an export list for a slice this build does not produce.
  Both fixed.
- **`NSAccessibilityRemoteUIElement`** gets darling-lol's `-init` grafted in ahead of
  `-initWithRemoteToken:`.
- **duct-tape RPC duplicates.** Both trees appended `fileport_makeport`/`fileport_makefd` to
  `generate-rpc-wrappers.py`, so the generated `rpc.h` declared each twice with two different
  call numbers. Resolved in darling-lol's favour end to end.
- **`vm_map.h`**: darling-lol's untyped `void *dtape_descriptor` is removed, because
  `duct-tape/src/memory.c` here is this tree's and uses the typed one.

## Duplicate definitions

Textual merge cleanliness says nothing about symbol-level duplication: when both trees fill
the same gap and the additions land at *different points* in a file, git merges them as text
with no conflict and the result defines one thing twice. Three dedupers run, each scoped so a
form that legitimately repeats on one side is left alone (the per-file ceiling is
`max(count in darling-lol, count in this tree)`):

- 17 duplicate Objective-C method definitions, scoped by `@implementation` *and* full
  selector — `insertSublayer:atIndex:` must not be confused with `insertSublayer:below:`, and
  `NSArray.m` legitimately defines `-count` in several `@implementation` blocks.
- 21 duplicate C/Objective-C function definitions, keyed on the *fully qualified* name:
  keying on the trailing identifier alone matched the 44 unrelated `processCall` handlers in
  `call.cpp` and deleted two real ones.
- 28 duplicate declaration blocks — enumerators, ivars, typedefs, constants and method
  declarations — driven by **clang's own diagnostics** rather than by a pattern. A regex is
  not reliable here: a trailing comment or a two-line signature defeats it, and a
  half-deleted declaration is worse than the duplicate. Replaying a build log is guarded, so
  a range is only deleted when it really does still contain the symbol clang named there.

Duplicate symbols that only the *linker* can see — the same definition added by each side to
a **different** file, so no textual conflict ever occurred — were resolved individually:
this tree's real `TSM*`/`*SecureEventInput` implementations replace darling-lol's four stubs
returning `-4` (and their now-redundant `SecureInput.c` leaves the build); their `noErr`
`LSSetDefaultHandlerForURLScheme` stub is kept over this tree's `kLSCannotSetInfoErr`,
because a client registering a URL scheme needs the call to succeed; the six
`kCLLocationAccuracy*` constants were identical, so theirs are kept in their own file; and for
`ICTransportTypeMassStorage` and `kCTFontCollectionRemoveDuplicatesOption`, where the two
sides' *values* differ, this tree's are kept.

## What is verified, and what is not

**Verified.** The tree configures with darling-lol's own flags and **builds to completion** —
`make` exits 0 with every target built, no compile errors, no duplicate symbols and no
undefined references. All 14 patches apply to a freshly prepared tree and round-trip
byte-for-byte. No file carries a conflict marker; no file's brace balance was changed by the
merge; no definition is duplicated beyond what one side already had; and no declaration/
implementation pair is split across sides except one benign case (darling-lol's
`block_suspend_gate` field, unused by this tree's `thread.c`).

**Run.** The merged build boots and runs. It was installed to a prefix under `$HOME`
(`-DCMAKE_INSTALL_PREFIX=$HOME/.local/darling-lol`) and run in a user namespace, so neither the
existing `/usr/local` installation nor `~/.darling` was touched:

```sh
DPREFIX=$HOME/.darling-lol-merged DARLING_HOST_UID=$(id -u) \
unshare --user --map-users=0:$(id -u):1 --map-users=1:100000:65536 \
               --map-groups=0:$(id -g):1 --map-groups=1:100000:65536 \
  $HOME/.local/darling-lol/bin/darling shell <command>
```

The real uid must map to namespace uid 0 — the launcher checks that it is *owned* by root in the
namespace, so `--map-auto --map-current-user --setuid=0` is refused despite `id -u` reporting 0 —
and the guest account needs the subordinate range mapped alongside it. Setup and every later
command have to run in the *same* namespace, since `darling shell` joins the container by opening
its mount namespace.

In that container: the prefix initialises, `launchd` starts, XPC services activate
(`opendirectoryd`, `trustd`), `uname -a` reports `Darwin 23.6.0 ... xnu-10063.141.2~1`, `sw_vers`
reports macOS 11.7.4, `hostinfo` reads the Mach host interfaces (32 processors), `sysctl`
answers `hw.ncpu`/`kern.ostype`/`kern.osrelease` through the duct-tape layer, guest `/bin/bash`
and `defaults` run, and `darling shutdown` exits cleanly. So the merged syscall, Mach and
Foundation plumbing works at runtime, not just at link time.

**Upstream's own probes.** Four of darling-lol's standalone probes in `tools/` were built
against this build's frameworks and run in that container:

| probe | result |
|---|---|
| `riot-appkit-pump-check` | **pass** — 200 events, 200 callbacks, 0 late polls, 8.9 ms |
| `riot-window-decorations-check` | **pass** — all 10 style-mask cases match, X11 `setStyleMask` live |
| `riot-window-layout-check` | **pass** — view/layer resize, native resize order, sibling resize, `setFrameSize:` hook, full layout |
| `riot-coretext-font-list-check` | **fail** — `localized font name is the family` |

So AppKit's event pump, the X11 window backend and NSView/NSWindow layout all work at runtime.

The CoreText failure is a real gap, measured rather than guessed: of 326 host font families, 49
do not instantiate to themselves and silently fall back to another family. Nine of those are
bitmap-only fonts (`arabic24.pcf.gz` and friends), where falling back is correct and the probe's
blanket assertion is simply too strict on a Linux host. The other **40 are outline TrueType
fonts that should have loaded** — almost all Nerd Font variants (`MesloLG*`, `FantasqueSansM*`,
each in Font/Mono/Propo flavours) plus Adwaita Mono and Adwaita Sans. The pattern suggests
families whose fontconfig-reported name does not match the name FreeType reads back from the
font, so enumeration offers a name that lookup cannot resolve.

Whether the merge caused this is **not** established. The `FT_FACE_FLAG_SCALABLE` rejection that
logs "FreeType font face is not scalable" is in the pinned base, present on all three sides, and
both the enumeration and the loading come from this tree's side of the font stack — so if
darling-lol's font path handled these families better, forcing that group here is what lost it.
The cheap comparison was not available: the Darling installed at `/usr/local` on this machine
predates its own working tree and cannot even link the probe (no
`CTFontDescriptorCreateMatchingFontDescriptor`). Settling it needs a pristine darling-lol build
to run the same probe against.

One other observation: after a probe exits, `darling shutdown` sometimes logs
`semaphore_timedwait failed (internally): -111`, `dserver_rpc_interrupt_enter failed with code
-111` and a `LOLSIGFAIL` backtrace. The container still shuts down and the session exits 0, but
the teardown path is not clean.

**Still not verified.** Nothing about the client itself, and no pixels were compared: the probes
exercise AppKit geometry, event delivery and window style, not rendered output. The game is not
installed, so the IOSurface/Chromium compositing path that the whole project turns on is still
untested.

**A note on the rootless install path.** `scripts/nix-idle.py` is fail-closed and cannot succeed
when run on the host: it raises on any process whose `/proc/<pid>/maps` it cannot read, and
`yama/ptrace_scope=1` makes `systemd --user` permanently unreadable, while its uid_map skip only
triggers from inside a Darling namespace. Treating `PermissionError` as unrelated fixes it. That
file is upstream's and was left unchanged here.

**Known losses.** Forcing a group to one side discards the other side's work in those files.
The notable ones: darling-lol's `IOObject`/`IOService` PROCMAP_QUERY optimisation for
`readMemory` and its `block_suspend_gate` suspension fix are not in this tree's
`process.cpp`/`thread.c`; their ~600 lines of CoreText and ~70 of `O2Font*` give way to this
tree's larger versions; this tree's iokitd IOSurface work and its unfinished file-backed
surface route are dropped entirely in favour of their Mach-port path.

## Regenerating

`tools/merge-pipeline/` holds the scripts that produced `patches-jsabella/`, in the order
`driver.sh` runs them. They clone each component from a Darling checkout, build
`base`/`lolbase`/`mine` branches, merge, resolve, graft, dedupe, audit, and finally emit the
patches. Every judgement call above is encoded there with its reason, so the layer can be
rebuilt rather than hand-maintained. The paths at the top of each script point at the tree
they were run against and need adjusting.
