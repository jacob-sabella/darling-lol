"""Remove method definitions the merge ended up with twice.

Both trees filled the same Cocotron gaps for the same Electron client, so each added its own
-masksToBounds, -titleVisibility, -copyFamilyName and so on. Added at different points in a
file, those merge as text without conflict and leave the method defined twice, which does not
compile. Every affected file is in a subsystem darling-lol owns under the chosen policy, so
the copy that came from THIS tree is the one removed -- surgically, by definition, so the
other work in the same file (e.g. the -[NSView _setWindow:] drawable fix) survives.
"""
import pathlib, re, subprocess, collections, sys

WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
IMPL  = re.compile(r"^\s*@implementation\s+(\w+)")
END   = re.compile(r"^\s*@end")
START = re.compile(r"^\s*([+-])\s*\(")
PIECE = re.compile(r"(\w+)\s*:")

def blocks(lines):
    """Yield (class, +/-, selector, first_line, last_line) for each method DEFINITION."""
    cls = None
    i = 0
    while i < len(lines):
        l = lines[i]
        if IMPL.match(l): cls = IMPL.match(l).group(1); i += 1; continue
        if END.match(l):  cls = None;                   i += 1; continue
        mo = START.match(l)
        if not mo: i += 1; continue
        sig, j = l, i
        while j + 1 < len(lines) and "{" not in sig and ";" not in sig:
            j += 1; sig += " " + lines[j].strip()
        head = sig.split("{")[0]
        if "{" not in sig or ";" in head:
            i = j + 1; continue
        body = re.sub(r"\([^)]*\)", " ", head[1:])
        pieces = PIECE.findall(body)
        sel = ":".join(pieces) + ":" if pieces else (body.split() or [""])[0]
        # balance braces from the opening one to the end of the body
        depth, k = 0, i
        started = False
        while k < len(lines):
            depth += lines[k].count("{") - lines[k].count("}")
            if "{" in lines[k]: started = True
            if started and depth <= 0: break
            k += 1
        yield (cls, mo.group(1), sel, i, k)
        i = k + 1

def norm(s): return re.sub(r"\s+", " ", s).strip()

def side(box, ref, f):
    r = subprocess.run(["git", "-C", str(box), "show", "%s:%s" % (ref, f)],
                       capture_output=True, text=True)
    return norm(r.stdout) if r.returncode == 0 else ""

total = 0
for box in sorted(p for p in WORK.iterdir() if p.is_dir()):
    files = subprocess.run(["git", "-C", str(box), "diff", "--name-only", "base", "HEAD", "--"],
                           capture_output=True, text=True).stdout.split()
    for f in files:
        if not f.endswith((".m", ".mm")): continue
        p = box / f
        if not p.exists(): continue
        for _pass in range(200):
            lines = p.read_text(errors="replace").splitlines(keepends=True)
            bl = list(blocks([l.rstrip("\n") for l in lines]))
            bykey = collections.defaultdict(list)
            for cls, pm, sel, a, b in bl: bykey[(cls, pm, sel)].append((a, b))
            dupes = {k: v for k, v in bykey.items() if len(v) > 1}
            if not dupes: break
            lol_txt, mine_txt = side(box, "lolbase", f), side(box, "mine", f)
            # drop one occurrence per pass so line numbers stay valid
            k, occ = next(iter(dupes.items()))
            victim = None
            for a, b in occ:
                t = norm("".join(lines[a:b + 1]))
                if t and t in mine_txt and t not in lol_txt:
                    victim = (a, b); break
            if victim is None:
                victim = occ[-1]          # identical copies: keep the first
            a, b = victim
            while a > 0 and lines[a - 1].strip().startswith(("//", "/*", "*", "/**")):
                a -= 1                     # take the doc comment with it
            del lines[a:b + 1]
            while a < len(lines) and not lines[a].strip(): del lines[a]
            p.write_text("".join(lines))
            total += 1
            print("  %-22s %-38s %s%s %s" % (box.name[:22], f[-38:], k[1], k[0], k[2]))
print("\nremoved %d duplicate definition(s)" % total)
