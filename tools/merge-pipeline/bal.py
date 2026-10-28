"""Differential brace balance: only report files whose merged delta differs from every side.

Counting braces naively also counts the ones inside string literals and comments, so an
absolute imbalance proves nothing; a CHANGE in imbalance versus base/lol/mine does.
"""
import pathlib, subprocess
WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
def delta(t): return t.count("{") - t.count("}")
def show(box, ref, f):
    r = subprocess.run(["git","-C",str(box),"show","%s:%s"%(ref,f)],capture_output=True,text=True,errors="replace")
    return r.stdout if r.returncode==0 else None
bad=[]
for box in sorted(p for p in WORK.iterdir() if p.is_dir()):
    files = subprocess.run(["git","-C",str(box),"diff","--name-only","base","HEAD","--"],
                           capture_output=True,text=True,errors="replace").stdout.split()
    for f in files:
        if not f.endswith((".c",".m",".mm",".cpp",".h")): continue
        p = box/f
        if not p.exists(): continue
        dm = delta(p.read_text(errors="replace"))
        ds = [delta(t) for t in (show(box,r,f) for r in ("base","lolbase","mine")) if t is not None]
        if dm not in ds:
            bad.append((box.name,f,dm,ds))
print("files whose brace balance the merge CHANGED: %d"%len(bad))
for c,f,dm,ds in bad: print("   %-24s %-46s merged=%+d sides=%s"%(c[:24],f[-46:],dm,ds))
