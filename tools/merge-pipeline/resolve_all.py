"""Single reproducible resolution pass over every conflict.

Policy (chosen by the user): darling-lol wins the rendering/font/compositing stack, which is
the code their tree plays at ~130 FPS with; this tree wins the syscall/plumbing layer, where
it has fixes darling-lol lacks. Decided case by case where neither label fits.

Per conflict REGION, not per file, so a contested file keeps everything git merged cleanly.
A region both sides only ADDED to is unioned -- unless both added the same symbol, in which
case the union would define it twice and the winner takes the region instead.
"""
import pathlib, re, subprocess, collections, sys

S = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                 "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad")
WORK = S / "merge"

# Verified individually; the reason is recorded in the fork's MERGE-NOTES.md.
OVERRIDE = {
    ("root", "src/frameworks/Carbon/HIToolbox/src/Events.cpp"): "you",
    ("src_external_corefoundation", "NSArray.m"): "you",
    ("src_external_corefoundation", "NSDictionary.m"): "you",
    ("src_external_cocotron", "AppKit/NSAccessibilityRemoteUIElement.m"): "you",
    ("src_external_cocotron", "AppKit/private-include/AppKit/NSAccessibilityRemoteUIElement.h"): "you",
    ("src_external_xnu", "darling/src/libsystem_kernel/emulation/src/xnu_syscall/bsd/impl/network/accept.c"): "you",
    ("src_external_Libinfo", "darling-resolver/resolver.c"): "lol",
    # Their fileport scopes the port to the owning task and handles the process
    # lifecycle; ours is task-agnostic, which is wrong for multi-process Chromium.
    ("src_external_darlingserver", "duct-tape/src/fileport.c"): "lol",
    ("src_external_xnu", "darling/src/libsystem_kernel/emulation/src/xnu_syscall/bsd/impl/bsdthread/bsdthread_register.c"): "lol",
    ("src_external_xnu", "darling/src/libsystem_kernel/emulation/src/linux_premigration/signal/sigexc.c"): "lol",
    ("root", "src/sandbox/sandbox.c"): "lol",
    ("root", "src/startup/mldr/elfcalls/elfcalls.c"): "lol",
    ("root", "src/frameworks/CoreMedia/include/CoreMedia/CMFormatDescription.h"): "lol",
    ("src_external_cocotron", "AppKit/nib.subproj/NSNib.m"): "lol",
    ("src_external_libnotify", "notifyd/CMakeLists.txt"): "lol",
}
GROUPS = [
    (r"CoreText/|Onyx2D/|NSFont|CGFont",                      "lol"),
    (r"QuartzCore/",                                          "lol"),
    (r"X11\.backend/",                                        "lol"),
    (r"IOSurface|OpenGL",                                     "lol"),
    (r"CoreVideo",                                            "lol"),
    (r"AVFoundation|ImageCaptureCore|MediaAccessibility",     "lol"),
    (r"AppKit/|CoreGraphics/",                                "lol"),
    (r"/xattr/|conversion/xattr",                             "you"),
    (r"guarded|fileport|mac_syscall",                         "you"),
    (r"SystemConfiguration|dnsinfo",                          "you"),
    (r"^src/(message|process)\.cpp|duct-tape/",               "you"),
    (r"IOPMrootDomain|IOInterestNotification|IOObject",       "you"),
    (r"src/(event|pipe)\.m",                                  "you"),
    (r"CoreAudio",                                            "you"),
]
BY_COMP = {"src_external_libkqueue": "you", "src_external_iokitd": "you",
           "src_external_libtrace": "you", "src_external_xnu": "you",
           "src_external_darlingserver": "you", "src_external_configd": "you",
           "src_external_libxpc": "you", "src_external_compiler-rt": "you"}

OBJC = re.compile(r"^\s*[+-]\s*\([^)]*\)\s*(\w+)")
CFUN = re.compile(r"^[A-Za-z_][\w\s\*]*?\b(\w+)\s*\([^;]*$")
RX = re.compile(r"^<<<<<<< [^\n]*\n(.*?)(?:^\|\|\|\|\|\|\|[^\n]*\n(.*?))?^=======\n(.*?)^>>>>>>> [^\n]*\n",
                re.S | re.M)

def winner(comp, f):
    if (comp, f) in OVERRIDE: return OVERRIDE[(comp, f)], "verified"
    for rx, who in GROUPS:
        if re.search(rx, f): return who, "subsystem"
    if comp in BY_COMP: return BY_COMP[comp], "subsystem"
    return "lol", "default"

def syms(box, side, f):
    d = subprocess.run(["git", "-C", str(box), "diff", "base", side, "--", f],
                       capture_output=True, text=True).stdout
    out = set()
    for l in d.splitlines():
        if not l.startswith("+") or l.startswith("+++"): continue
        s = l[1:]
        if s.lstrip().startswith(("//", "/*", "*")): continue
        for rx in (OBJC, CFUN):
            mo = rx.match(s)
            if mo: out.add(mo.group(1)); break
    return out

tally, log = collections.Counter(), []
for box in sorted(WORK.iterdir()):
    cf = box / ".conflicts"
    if not cf.exists(): continue
    for f in [x for x in cf.read_text().split() if x]:
        who, why = winner(box.name, f)
        p = box / f
        in_base = subprocess.run(["git", "-C", str(box), "cat-file", "-e", "base:" + f],
                                 capture_output=True).returncode == 0
        if not in_base:
            subprocess.run(["git", "-C", str(box), "checkout",
                            "lolbase" if who == "lol" else "mine", "--", f], check=True)
            tally[who + "/whole-file"] += 1
            log.append((box.name, f, who, why, "add/add"))
            continue
        # Whole file from the winner, NOT per region. Mixing regions inside one file
        # interleaves two implementations of the same function whenever both sides
        # rewrote a body while leaving the signature as context -- which no symbol-level
        # check can see, and which produced code that called vchroot_expand twice and
        # issued the removexattr syscall twice. Verified against a real build.
        subprocess.run(["git", "-C", str(box), "checkout",
                        "lolbase" if who == "lol" else "mine", "--", f], check=True)
        tally[who + "/whole-file"] += 1
        log.append((box.name, f, who, why, "whole-file"))

# ---------------------------------------------------------------------------
# Header union pass.
#
# Whole-file resolution is right for an implementation, where taking half of each
# side interleaves two versions of one function. A header is not like that: it is
# a list of declarations, and both sides only ever appended to it. Picking a side
# there throws away the other side's declarations while its implementation -- which
# merged cleanly, as a union of both sides' code -- still uses them, and the build
# fails with 'use of undeclared identifier' far away from the header. So contested
# headers are re-merged three-way instead, and the duplicate declarations that
# produces are removed afterwards from clang's own diagnostics (fixdup.py).
import tempfile

unioned = 0
for box in sorted(WORK.iterdir()):
    cf = box / ".conflicts"
    if not cf.exists():
        continue
    for f in [x for x in cf.read_text().split() if x]:
        if not f.endswith((".h", ".hpp", ".hh")):
            continue
        blobs = {}
        for ref in ("base", "lolbase", "mine"):
            r = subprocess.run(["git", "-C", str(box), "show", f"{ref}:{f}"],
                               capture_output=True)
            if r.returncode != 0:
                blobs = None
                break
            blobs[ref] = r.stdout
        if not blobs:
            continue
        tmp = {}
        for ref, data in blobs.items():
            h = tempfile.NamedTemporaryFile(delete=False)
            h.write(data)
            h.close()
            tmp[ref] = h.name
        # Both sides append to these headers, usually at the very end of the same
        # class, so a plain three-way merge conflicts every time. Where NEITHER side
        # deleted a line, keeping both sides' lines is exactly right -- nothing can
        # be lost that way, and it is only a declaration list. If either side did
        # delete something it rewrote rather than extended the header, and then the
        # whole-file choice above stands.
        dels = 0
        for ref in ("lolbase", "mine"):
            out = subprocess.run(["git", "-C", str(box), "diff", "--numstat",
                                  "base", ref, "--", f],
                                 capture_output=True, text=True).stdout.split()
            if len(out) >= 2 and out[1].isdigit():
                dels += int(out[1])
        mode = "--union" if dels == 0 else "--diff3"
        r = subprocess.run(["git", "merge-file", "-p", mode,
                            tmp["lolbase"], tmp["base"], tmp["mine"]],
                           capture_output=True)
        ok = r.returncode == 0 or mode == "--union"
        if ok:
            # A union inside an @interface can interleave two class bodies and
            # leave the file structurally broken (NSSpeechSynthesizer.h came out
            # with a duplicate @interface and no matching @end). Only accept a
            # result whose scope and conditional nesting still balance the way
            # both inputs did; otherwise the whole-file choice above stands.
            def shape(data):
                s = data.decode("utf-8", "replace")
                opens = len(re.findall(r"^\s*@(?:interface|implementation|protocol)\b",
                                       s, re.M))
                ends = len(re.findall(r"^\s*@end\b", s, re.M))
                ifs = len(re.findall(r"^\s*#\s*if", s, re.M))
                endifs = len(re.findall(r"^\s*#\s*endif", s, re.M))
                return (opens - ends, ifs - endifs)
            if shape(r.stdout) != shape(blobs["lolbase"]) or \
               shape(r.stdout) != shape(blobs["mine"]):
                ok = False
                print("   union rejected (structure changed):", f[-58:])
        if ok:
            (box / f).write_bytes(r.stdout)
            subprocess.run(["git", "-C", str(box), "add", "--", f], check=True)
            unioned += 1
        for n in tmp.values():
            pathlib.Path(n).unlink()

print("headers re-merged as a union of both sides:", unioned)

print("%-24s %-46s %-4s %-9s %s" % ("component", "file", "win", "why", "mode"))
print("-" * 104)
for c, f, who, why, mode in log:
    if why != "subsystem":
        print("%-24s %-46s %-4s %-9s %s" % (c[:24], f[-46:], who, why, mode))
print("-" * 104)
print(dict(tally))
print("total resolved:", sum(tally.values()))


# ---------------------------------------------------------------------------
# Coupled-group pass.
#
# Whole-file resolution is per file, so it happily takes a header from one side
# and its implementation from the other. Where both sides built the SAME feature
# the two halves then disagree about types, struct members and selectors, and the
# build fails in the consumer rather than at the seam. Worse, a feature can span
# two components (iokitd is the IOSurface server, src/frameworks/IOSurface the
# client library, and they share a wire struct), so the unit of choice has to be
# the feature, not the file. Each entry forces one side across a whole group and
# drops files that exist only on the losing side.
GROUP_FORCE = [
    # Both sides implemented IOKit interest notifications independently -- mine as
    # IOInterestNotification.cpp, theirs as .mm, each with its own header, and the
    # merge kept both files and both CMake entries. Theirs is the complete one
    # (286 lines vs 41, with retry, port liveness and message flushing) and its
    # IOObject/IOService changes subsume mine: their ~IOObject cancels the source
    # with a handler that captures only the port, and their is_io_service_open_extended
    # deallocates the properties memory and task right that mine leaks.
    ("src_external_iokitd", r".*", "lol", ["src/IOInterestNotification.cpp"]),
    # The IOSurface client library must come from the same side as the iokitd server:
    # the two sides' wire structs differ (theirs has no allocSize member), and theirs
    # is the API-faithful Mach-port path (IOSurfaceCreateMachPort /
    # IOSurfaceLookupFromMachPort) that multi-process Chromium actually uses, where
    # mine went down a file-backed route that is still unfinished.
    ("root", r"^src/frameworks/IOSurface/", "lol", []),
    # fileport already resolved to theirs for process-lifetime reasons; call.cpp and
    # duct-tape.h have to agree with it on dtape_fileport_makeport's arity.
    ("src_external_darlingserver",
     r"^(src/call\.cpp|duct-tape/include/darlingserver/duct-tape\.h|duct-tape/src/fileport\.c)$",
     "lol", []),
    # Theirs rewrote CGDirectDisplay.m (120+/38-); mine's additions conflict with
    # their header's prototypes for CGDisplayIsBuiltin/CGDisplayUsesForceToGray.
    ("src_external_cocotron", r"^CoreGraphics/(include/CoreGraphics/)?CGDirectDisplay\.(h|m)$",
     "lol", []),
    # Here it is the other way round: the .mm is mine (116+/7-) and needs the
    # kTISPropertyInputSource* constants that only my header declares.
    ("root", r"^src/frameworks/Carbon/HIToolbox/(include/HIToolbox|src)/TextInputSources\.(h|mm)$",
     "mine", []),
    # message.hpp is theirs and declares initializeServerCredentials() and
    # pushAndSend(); only their message.cpp defines them, and their darlingserver.cpp
    # and server.cpp call them -- with mine's message.cpp the server failed to link.
    # My one-line fix to the same file is re-applied as a graft in handfix.py.
    ("src_external_darlingserver",
     r"^(internal-include/darlingserver/message\.hpp|src/message\.cpp)$", "lol", []),
    # Four Cocotron pairs where the header is mine alone and declares what mine's
    # implementation defines, but the .m had gone to theirs.
    ("src_external_cocotron", r"^QuartzCore/CATransactionGroup\.(h|m)$", "mine", []),
    ("src_external_cocotron", r"^(CoreGraphics/CGContext\.m|CoreGraphics/include/CoreGraphics/CGContext\.h)$",
     "mine", []),
    # CoreText is one tightly coupled subsystem -- CTFont, KTFont and
    # CTFontDescriptor share internal structs and private functions -- and
    # resolution had split it, leaving mine's CTFontManager.m calling a
    # CTFontDescriptorCreateWithNameAndSize that only mine's other files declare
    # and define. Mine is the larger body here (~1140 added lines against ~600),
    # so the group goes to mine; their CMakeLists stays, because both sides made
    # the same source-list change and theirs additionally links fontconfig.
    ("src_external_cocotron", r"^CoreText/(?!CMakeLists\.txt$).*", "mine", []),
    # The font stack reaches past CoreText: mine's CTFontDescriptor.m and CTFont.m
    # call O2FontCopyFaceList, the O2FontFace* keys and CGFontCopyTableTags, which
    # only mine's Onyx2D and CGFont define, so CoreText linked against nothing.
    # Mine is much the larger side here too (342 lines against 51 in
    # O2Font_freetype.m, 144 against 17 in O2Font.m).
    ("src_external_cocotron",
     r"^(Onyx2D/O2Font(_freetype)?\.m|Onyx2D/include/Onyx2D/O2Font(_freetype)?\.h"
     r"|CoreGraphics/CGFont\.m|CoreGraphics/include/CoreGraphics/CGFont\.h)$", "mine", []),
    ("src_external_cocotron", r"^(AppKit/NSScreen\.m|AppKit/include/AppKit/NSScreen\.h)$",
     "mine", []),
    # Both sides added touch-bar support to NSResponder, but with different types:
    # mine is typed (NSTouchBar *, plus makeTouchBar), theirs is id-based. That is a
    # genuine conflict rather than two appends, so the header could not be unioned
    # and fell back to theirs -- leaving the merged .m calling makeTouchBar with
    # NSTouchBar undeclared. Mine's typed pair wins; their otherMouse* declarations
    # are grafted back in handfix.py, since their .m defines them.
    ("src_external_cocotron", r"^(AppKit/NSResponder\.m|AppKit/include/AppKit/NSResponder\.h)$",
     "mine", []),
    # They never touched this header, so resolving it to "theirs" meant resolving it
    # to base and dropping my TSM declarations while keeping my definitions of them.
    ("root", r"^src/frameworks/Carbon/HIToolbox/(include/HIToolbox|src)/TextServices\.(h|c)$",
     "mine", []),
]

import re as _re
forced = collections.Counter()
for boxname, pat, side, drops in GROUP_FORCE:
    box = WORK / boxname
    if not box.exists():
        print("GROUP_FORCE: no such component", boxname); continue
    rx = _re.compile(pat)
    ref = "lolbase" if side == "lol" else "mine"
    cand = set()
    for other in ("lolbase", "mine"):
        out = subprocess.run(["git", "-C", str(box), "diff", "--name-only", "base", other, "--"],
                             capture_output=True, text=True).stdout.split()
        cand.update(f for f in out if rx.match(f))
    for f in sorted(cand):
        if f in drops:
            subprocess.run(["git", "-C", str(box), "rm", "-q", "-f", "--ignore-unmatch", "--", f])
            forced[boxname + "/dropped"] += 1
            continue
        have = subprocess.run(["git", "-C", str(box), "cat-file", "-e", ref + ":" + f],
                              capture_output=True).returncode == 0
        if have:
            subprocess.run(["git", "-C", str(box), "checkout", ref, "--", f], check=True)
            forced[boxname + "/" + side] += 1
        else:
            # the losing side invented this file; it has no place in the chosen group
            subprocess.run(["git", "-C", str(box), "rm", "-q", "-f", "--ignore-unmatch", "--", f])
            forced[boxname + "/dropped"] += 1

print("coupled-group pass:", dict(forced))
