import json, pathlib, subprocess
LOL=pathlib.Path.home()/"Projects/darling-lol"
SRC=LOL/"build/darling-src"
man=json.loads((LOL/"upstream/manifest.json").read_text())
def sh(a,cwd): return subprocess.run(a,cwd=str(cwd),capture_output=True,text=True,errors="replace")
bad=[]
for c in man["components"]:
    repo = SRC if c["path"]=="." else SRC/c["path"]
    if not (repo/".git").exists():
        bad.append((c["path"],"no .git")); continue
    sh(["git","checkout","-f","-q",c["revision"]],repo)
    sh(["git","clean","-fdq"],repo)
    head=sh(["git","rev-parse","HEAD"],repo).stdout.strip()
    dirty=sh(["git","status","--porcelain"],repo).stdout.strip()
    # submodule gitlinks show as modified in the superproject; ignore directories
    lines=[l for l in dirty.splitlines() if not (repo/l[3:]).is_dir()]
    if head!=c["revision"]: bad.append((c["path"],"HEAD %s != pin"%head[:9]))
    elif lines: bad.append((c["path"],"still dirty: %d path(s) e.g. %s"%(len(lines),lines[0][:60])))
print("components reset:",len(man["components"]))
if bad:
    print("PROBLEMS:")
    for p,why in bad: print("   %-34s %s"%(p[:34],why))
else:
    print("all components pristine at their pinned revision")
