"""Verify each overlay patch reproduces the merged tree exactly from darling-lol's state."""
import json, pathlib, subprocess, shutil
HOME=pathlib.Path.home(); LOL=HOME/"Projects/darling-lol"
WORK=pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
RT=WORK.parent/"roundtrip"
if RT.exists(): shutil.rmtree(RT)
RT.mkdir()
man=json.loads((LOL/"upstream/manifest.json").read_text())
ok=fail=0
for c in man["components"]:
    name="root" if c["path"]=="." else c["path"].replace("/","_")
    box=WORK/name
    patch=LOL/"patches-jsabella"/pathlib.Path(c["patch"]).name
    if not box.exists() or not patch.exists(): continue
    wt=RT/name
    subprocess.run(["git","-C",str(box),"worktree","add","-q","--detach",str(wt),"lolbase"],
                   capture_output=True,check=True)
    txt=patch.read_text().replace("@HOST_HOME@",str(HOME)).replace("@GUEST_USER@","jsabella")
    r=subprocess.run(["git","-C",str(wt),"apply","--whitespace=nowarn","-"],input=txt,
                     text=True,capture_output=True)
    if r.returncode:
        print("  %-30s APPLY FAILED: %s"%(c["path"][:30],(r.stdout+r.stderr)[-160:])); fail+=1
    else:
        subprocess.run(["git","-C",str(wt),"add","-A"],capture_output=True)
        got=subprocess.run(["git","-C",str(wt),"write-tree"],capture_output=True,text=True).stdout.strip()
        want=subprocess.run(["git","-C",str(box),"rev-parse","HEAD^{tree}"],capture_output=True,text=True).stdout.strip()
        if got==want: print("  %-30s OK"%c["path"][:30]); ok+=1
        else:
            d=subprocess.run(["git","-C",str(box),"diff","--stat",want,got],capture_output=True,text=True,errors="replace").stdout
            print("  %-30s TREE MISMATCH\n%s"%(c["path"][:30],d[-400:])); fail+=1
    subprocess.run(["git","-C",str(box),"worktree","remove","--force",str(wt)],capture_output=True)
print("\n%d reproduce exactly, %d failed"%(ok,fail))
