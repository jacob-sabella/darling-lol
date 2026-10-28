"""Differential duplicate-definition audit.

Counts (class, full-selector) definitions per file for base / darling-lol / this tree / the
merge, and reports only where the MERGE has more definitions than either side did. That way
pre-existing repeats, several @implementation blocks in one file, and overloaded selector
families cannot show up as false positives.
"""
import pathlib, re, subprocess, collections
WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
IMPL  = re.compile(r"^\s*@implementation\s+(\w+)")
END   = re.compile(r"^\s*@end")
START = re.compile(r"^\s*([+-])\s*\(")
PIECE = re.compile(r"(\w+)\s*:")

def defs(txt):
    """(class, +/-, selector) -> count, for method DEFINITIONS only."""
    out = collections.Counter()
    lines = txt.splitlines()
    cls = None
    for i, l in enumerate(lines):
        mo = IMPL.match(l)
        if mo: cls = mo.group(1); continue
        if END.match(l): cls = None; continue
        mo = START.match(l)
        if not mo: continue
        sig, j = l, i
        while j + 1 < len(lines) and "{" not in sig and ";" not in sig:
            j += 1; sig += " " + lines[j].strip()
        head = sig.split("{")[0]
        if "{" not in sig or ";" in head:
            continue                                   # a declaration, not a definition
        body = re.sub(r"\([^)]*\)", " ", head[1:])     # drop every type in parens
        pieces = PIECE.findall(body)
        sel = ":".join(pieces) + ":" if pieces else (body.split() or [""])[0]
        out[(cls, mo.group(1), sel)] += 1
    return out

def show(box, ref, f):
    r = subprocess.run(["git", "-C", str(box), "show", "%s:%s" % (ref, f)],
                       capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else ""

bad = []
for box in sorted(p for p in WORK.iterdir() if p.is_dir()):
    # EVERY file both sides touched, not just the conflicted ones: git merges text, so two
    # implementations of the same method added at different places in a file merge cleanly
    # and silently define it twice.
    import subprocess as sp
    files = sp.run(["git","-C",str(box),"diff","--name-only","base","HEAD","--"],
                   capture_output=True,text=True,errors="replace").stdout.split()
    for f in files:
        if not f.endswith((".m", ".mm")): continue
        p = box / f
        if not p.exists(): continue
        merged = defs(p.read_text(errors="replace"))
        sides = [defs(show(box, r, f)) for r in ("base", "lolbase", "mine")]
        for key, n in merged.items():
            ceiling = max(s.get(key, 0) for s in sides)
            if n > ceiling:
                bad.append((box.name, f, key, n, ceiling))

print("definitions the MERGE duplicated beyond either side: %d" % len(bad))
for c, f, key, n, ce in bad:
    cls, pm, sel = key
    print("   %-22s %-40s %s%s %s  merged=%d max(base,lol,mine)=%d"
          % (c[:22], f[-40:], pm, cls, sel, n, ce))
