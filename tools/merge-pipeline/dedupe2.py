"""Remove C / Objective-C / generator-list definitions the merge ended up with twice.

Differential and name-based: for each file, a definition NAME is over-defined when it
appears more times than in base, darling-lol or this tree. The first occurrence is kept and
later ones removed whole (brace-balanced for bodies, single line for declarations), so this
cannot invent a count that no input side had.
"""
import pathlib, re, subprocess, collections, sys

WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
OBJC   = re.compile(r"^\s*[+-]\s*\([^)]*\)\s*(\w+)")
CFUNC  = re.compile(r"^[A-Za-z_][\w\s\*&<>,]*?\b([A-Za-z_][\w:~]*)\s*\(")  # full qualified name
CONSTD = re.compile(r"^\s*(?:[A-Za-z_]\w*\s+)*?(?:const\s+)?[A-Za-z_]\w*\s*\*?\s*const\s+(\w+)\s*=")
CONST2 = re.compile(r"^\s*const\s+[A-Za-z_]\w*\s+(\w+)\s*=")
DECL   = re.compile(r"^\s*(?:extern|APPKIT_EXPORT|COREGRAPHICS_EXPORT|FOUNDATION_EXPORT|@class)\b.*?(\w+)\s*;")
ENUMM  = re.compile(r"^\s*(\w+)\s*=\s*\d+U?,\s*$")

def defs(lines):
    """[(name, kind, first, last)] for every definition-like construct."""
    out, i = [], 0
    while i < len(lines):
        l = lines[i]
        for rx, kind in ((OBJC, "objc"), (CONSTD, "const"), (CONST2, "const"),
                         (DECL, "decl"), (ENUMM, "enum")):
            mo = rx.match(l)
            if mo:
                j = i
                while j < len(lines) and ";" not in lines[j] and "{" not in lines[j]:
                    j += 1
                if kind == "objc":
                    break
                out.append((mo.group(1), kind, i, min(j, len(lines) - 1))); i = min(j, len(lines)-1) + 1
                break
        else:
            mo = CFUNC.match(l) if l and not l[0].isspace() else None
            om = OBJC.match(l)
            if mo or om:
                sig, j = l, i
                while j + 1 < len(lines) and "{" not in sig and ";" not in sig:
                    j += 1; sig += " " + lines[j].strip()
                head = sig.split("{")[0]
                if "{" in sig and ";" not in head:
                    depth, k, started = 0, i, False
                    while k < len(lines):
                        depth += lines[k].count("{") - lines[k].count("}")
                        if "{" in lines[k]: started = True
                        if started and depth <= 0: break
                        k += 1
                    name = (om or mo).group(1)
                    out.append((name, "body", i, min(k, len(lines)-1))); i = min(k, len(lines)-1) + 1
                    continue
            i += 1
            continue
        i += 1
    return out

def show(box, ref, f):
    r = subprocess.run(["git","-C",str(box),"show","%s:%s"%(ref,f)],
                       capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode==0 else ""

total = 0
for box in sorted(p for p in WORK.iterdir() if p.is_dir()):
    files = subprocess.run(["git","-C",str(box),"diff","--name-only","base","HEAD","--"],
                           capture_output=True,text=True,errors="replace").stdout.split()
    for f in files:
        if not f.endswith((".c",".m",".mm",".cpp",".h",".hpp")): continue
        p = box/f
        if not p.exists(): continue
        ceilings = None
        for _ in range(400):
            lines = p.read_text(errors="replace").splitlines(keepends=True)
            plain = [l.rstrip("\n") for l in lines]
            if ceilings is None:
                ceilings = collections.Counter()
                for ref in ("base","lolbase","mine"):
                    c = collections.Counter(n for n,_,_,_ in defs(show(box,ref,f).splitlines()))
                    for k,v in c.items(): ceilings[k]=max(ceilings[k],v)
            cur = defs(plain)
            cnt = collections.Counter(n for n,_,_,_ in cur)
            over = [n for n,v in cnt.items() if v > max(1, ceilings.get(n,0))]
            if not over: break
            name = over[0]
            occ = [d for d in cur if d[0]==name]
            _, kind, a, b = occ[-1]                     # keep the first, drop the last
            while a>0 and plain[a-1].strip().startswith(("//","/*","*")): a-=1
            del lines[a:b+1]
            while a < len(lines) and not lines[a].strip(): del lines[a]
            p.write_text("".join(lines)); total += 1
            print("  %-22s %-44s %s (%s)"%(box.name[:22], f[-44:], name, kind))
print("\nremoved %d over-definition(s)"%total)
