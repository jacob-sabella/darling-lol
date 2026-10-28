"""Report declaration/definition pairs that the merge took from different sides.

Whole-file resolution decides each file alone, so it will happily keep one side's
header and the other side's implementation. The two halves then disagree about
types, struct members, selectors or -- worst, because it survives compilation --
about which functions exist at all: a header declaring methods whose only
definitions live in the side that lost shows up as an undefined reference at link
time, thousands of lines into the build. Listing the split pairs up front is much
cheaper than finding them one relink at a time.
"""
import pathlib, subprocess, collections

WORK = pathlib.Path(__file__).resolve().parent / "merge"
HDR = (".h", ".hpp", ".hh")
IMP = (".c", ".cpp", ".cc", ".m", ".mm")


def sh(a, cwd):
    return subprocess.run(a, cwd=str(cwd), capture_output=True, text=True,
                          errors="replace").stdout


def side_of(box, f):
    """Which side's content the merge ended up with, by content hash."""
    cur = sh(["git", "-C", str(box), "show", "HEAD:" + f], box)
    if not cur:
        p = box / f
        if not p.exists():
            return "absent"
        cur = p.read_text(errors="replace")
    out = []
    for ref, name in (("lolbase", "lol"), ("mine", "mine")):
        if sh(["git", "-C", str(box), "show", f"{ref}:{f}"], box) == cur:
            out.append(name)
    if not out:
        return "mixed"
    return "+".join(out)


rows = []
for box in sorted(WORK.iterdir()):
    if not (box / ".git").exists():
        continue
    changed = set()
    for ref in ("lolbase", "mine"):
        changed.update(sh(["git", "-C", str(box), "diff", "--name-only", "base", ref, "--"],
                          box).split())
    groups = collections.defaultdict(list)
    for f in changed:
        p = pathlib.PurePath(f)
        if p.suffix in HDR + IMP:
            groups[p.stem].append(f)
    for stem, fs in sorted(groups.items()):
        if len(fs) < 2:
            continue
        sides = {f: side_of(box, f) for f in fs}
        kinds = {f: ("hdr" if pathlib.PurePath(f).suffix in HDR else "imp") for f in fs}
        # only interesting when a header and an implementation disagree
        hs = {sides[f] for f in fs if kinds[f] == "hdr"}
        is_ = {sides[f] for f in fs if kinds[f] == "imp"}
        if not hs or not is_:
            continue
        decided = {s for s in hs | is_ if s in ("lol", "mine")}
        if len(decided) > 1:
            rows.append((box.name, stem, sides, kinds))

if not rows:
    print("no declaration/definition pair was taken from different sides")
else:
    print("SPLIT PAIRS -- a header and its implementation came from different sides:")
    for box, stem, sides, kinds in rows:
        print("  %-26s %s" % (box[:26], stem))
        for f in sorted(sides):
            print("      %-4s %-62s %s" % (kinds[f], f[-62:], sides[f]))
print("\n%d split pair(s)" % len(rows))
