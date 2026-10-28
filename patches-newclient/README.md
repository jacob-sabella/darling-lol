# Riot Client 142.0.1.5150 blockers

The Riot Client self-updates on launch. The release it pulled on 2026-10-27
(`6E813D498F26C657`, client `142.0.1.5150`) is built against a newer macOS SDK
and a newer Electron than the one this project has been developed against, and
it does not load on Darling. This directory records what it needs.

These patches are **not** part of the merge in `patches-jsabella/`. They apply to
the same component (`darling`) and are kept separate because the merge pipeline
regenerates `patches-jsabella/*.patch` from its merge boxes.

## What changed between releases

The client in a prefix from 2026-10-01 asks for `QLPreviewPanel` from `Quartz`
(which Darling has) and weak-links `MPNowPlayingInfoCenter`. Nothing else.

The 2026-10-27 release **hard-links five frameworks Darling does not have at
all** — not in its source tree, not in any install:

| framework | symbols the Electron Framework imports |
|---|---|
| QuickLookUI | `QLPreviewPanel` |
| Accessibility | `AXCustomContent`, `AXPrefersNonBlinkingTextInsertionIndicator`(+`…DidChangeNotification`) |
| CoreHaptics | `CHHapticPattern`, `CHHapticEvent`, `CHHapticEventParameter`, `CHHapticDynamicParameter` + 5 ID constants |
| CoreML | `MLModel`, `MLModelConfiguration`, `MLMultiArray`, `MLFeatureValue`, `MLPredictionOptions`, `MLComputePlan`, and the three compute-device classes |
| MediaPlayer | `MPNowPlayingInfoCenter`, `MPRemoteCommandCenter`, `MPMediaItemArtwork` + 8 property constants |

`QuickLookThumbnailing` is also absent but weak-linked, so it costs nothing.

`darling-stub-frameworks.patch` adds all five as stub frameworks: each exports
exactly those symbols and nothing else, so dyld can bind the image. Every message
to a stub class is absorbed and logged (Darling's `forwardInvocation:` idiom,
with a pointer-sized signature so an object-returning selector gets `nil`). None
of the features behind them — haptics, Core ML, Now Playing, Quick Look previews,
accessibility custom content — are reached by the client.

`src/libaccessibility` already owns the CMake target name `Accessibility`, so the
framework passes `TARGET_NAME AccessibilityFramework`.

## Where it still stops

With all five in place the client launcher runs, self-updates, verifies its
install, opens its 392x488 splash window, and hands off to
`libRiotClientFoundation.dylib`. The Electron Framework then aborts on:

```
dyld: Symbol not found: _OBJC_CLASS_$_NSConstantIntegerNumber
```

That is the next wall, and it is a different kind of problem. The compiler that
built this release emits **constant literal objects** — `NSConstantIntegerNumber`,
`NSConstantDoubleNumber`, `NSConstantArray`, `NSConstantDictionary`, and the
`__NSArray0__struct` / `__NSDictionary0__struct` empty-collection singletons —
as statically allocated instances in the client's own `__DATA`. Foundation and
CoreFoundation have to provide those classes with Apple's exact instance layout,
because the client's static objects *are* instances of them. A stub class would
load and then corrupt or crash on first use, so these need real implementations.

## The full picture

`missing-symbols.txt` is the output of `symsweep.py` over every Mach-O in the
client bundle: 121 symbols that the installed runtime does not define, grouped by
the framework each one is imported from. Most are functions, which Darling binds
lazily — they only abort if the client actually calls them, which is why the
launcher got as far as it did. The ones that abort at load are the
`_OBJC_CLASS_$_*` class references and the `_k…` data constants.

```sh
find "$PREFIX/Users/Shared/Riot Games/Riot Client.app" -type f \( -perm -u+x -o -name '*.dylib' \) -print0 \
  | xargs -0 python3 -I symsweep.py
```

`symsweep.py` resolves each import against the dylib its two-level-namespace
ordinal names, following `LC_REEXPORT_DYLIB` transitively, and skips weak
imports. It reports versioned install names (`libSystem.B.dylib`,
`libc++.1.dylib`) as "not installed" rather than guessing, because `nm` prints
the unversioned leaf; check those by hand. `machodeps.py` lists an image's
`LC_LOAD_DYLIB` entries and marks the weak ones.

## Note for an existing prefix

A prefix still holding the older client has not updated *yet*. The update is
Riot's, triggered on launch, and it is not optional — so a working prefix will
hit this wall the next time the client is started.
