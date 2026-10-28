"""Differential line-multiset audit, restricted to definition-shaped lines.

Objective-C methods and C functions were only two shapes of "it ended up in there twice".
Both trees also appended the same `typedef NS_ENUM`, the same enum member, the same struct
field, the same extern and the same entry to a code generator's list. Counting LINES and
reporting only those the merge has MORE of than any input side catches all of it without
knowing any language; the DEFISH filter keeps ordinary repeated statements out.
"""
import pathlib, re, subprocess, collections

WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
SKIP = re.compile(r"^\s*(//|/\*|\*|#endif|#else|$)")
DEFISH = re.compile(
    r"typedef\s"                      # typedef NS_ENUM(...)
    r"|^\s*(?:extern|static)\s"       # extern / static declarations
    r"|_EXPORT\s"                     # APPKIT_EXPORT / COREGRAPHICS_EXPORT ...
    r"|@class\s|@interface\s"
    r"|^\s*const\s"
    r"|\bconst\s+\w+\s*\*?\s*\w+\s*=" # const CFStringRef kFoo = ...
    r"|=\s*\d+U?,\s*$"                # enum member
    r"|\)\s*\{\s*$"                   # function definition opener
)

def counts(text):
    c = collections.Counter()
    for l in text.splitlines():
        s = l.strip()
        if len(s) < 16 or SKIP.match(l):
            continue
        if not re.search(r"[A-Za-z_]\w\w", s):
            continue
        c[s] += 1
    return c

def show(box, ref, f):
    r = subprocess.run(["git", "-C", str(box), "show", "%s:%s" % (ref, f)],
                       capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else ""

bad = collections.defaultdict(list)
for box in sorted(p for p in WORK.iterdir() if p.is_dir()):
    files = subprocess.run(["git", "-C", str(box), "diff", "--name-only", "base", "HEAD", "--"],
                           capture_output=True, text=True, errors="replace").stdout.split()
    for f in files:
        if not f.endswith((".c", ".m", ".mm", ".cpp", ".h", ".hpp", ".py")):
            continue
        p = box / f
        if not p.exists():
            continue
        merged = counts(p.read_text(errors="replace"))
        sides = [counts(show(box, r, f)) for r in ("base", "lolbase", "mine")]
        for line, n in merged.items():
            ceiling = max(s.get(line, 0) for s in sides)
            if n >= 2 and n > ceiling and DEFISH.search(line):
                bad[(box.name, f)].append((line, n, ceiling))

print("files with a definition duplicated beyond either side: %d" % len(bad))
for (c, f), items in sorted(bad.items()):
    print("\n  %s / %s" % (c, f))
    for line, n, ce in items[:5]:
        print("      x%d (max %d): %s" % (n, ce, line[:84]))
