"""Final audit of the merged trees: no conflict markers, no symbol defined twice.

Checks the RESULT, not the diffs -- an Objective-C method defined twice in one
@implementation, or a C function defined twice in one file, does not compile.
"""
import pathlib, re, collections
WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
SRC = (".c", ".m", ".mm", ".cpp", ".h", ".hpp")
METH = re.compile(r"^\s*([+-])\s*\([^)]*\)\s*([A-Za-z_]\w*)")      # def or decl
CFUN = re.compile(r"^(?!\s)(?:[A-Za-z_][\w\s\*]*?\s)?\**([A-Za-z_]\w*)\s*\([^;]*\)\s*\{?\s*$")

markers, dups = [], []
for box in sorted(p for p in WORK.iterdir() if p.is_dir()):
    conf = (box / ".conflicts")
    files = [f for f in conf.read_text().split() if f] if conf.exists() else []
    for f in files:
        p = box / f
        if not p.exists():
            continue
        txt = p.read_text(errors="replace")
        if "<<<<<<<" in txt or ">>>>>>>" in txt or "|||||||" in txt:
            markers.append((box.name, f))
        if not f.endswith(SRC):
            continue
        # method DEFINITIONS only: a '{' on the same line or the next non-blank one
        lines = txt.splitlines()
        defs = collections.Counter()
        for i, l in enumerate(lines):
            mo = METH.match(l)
            if mo:
                tail = l
                j = i
                while j + 1 < len(lines) and "{" not in tail and ";" not in tail:
                    j += 1; tail += " " + lines[j].strip()
                if "{" in tail and ";" not in tail.split("{")[0]:
                    defs[mo.group(1) + mo.group(2)] += 1
        for k, v in defs.items():
            if v > 1:
                dups.append((box.name, f, k, v))

print("files still carrying conflict markers: %d" % len(markers))
for c, f in markers: print("   %s  %s" % (c, f))
print("\nsymbols defined more than once in a merged file: %d" % len(dups))
for c, f, k, v in dups: print("   %-24s %-48s %s x%d" % (c[:24], f[-48:], k, v))
