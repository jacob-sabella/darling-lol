import json, pathlib, subprocess, re
HOME=pathlib.Path.home(); LOL=HOME/"Projects/darling-lol"
WORK=pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
OUT=LOL/"patches-jsabella"; OUT.mkdir(exist_ok=True)
# Clear stale patches first. A component whose overlay became empty (iokitd, once
# its whole interest-notification group resolved to darling-lol) would otherwise
# keep the previous run's patch file and overlay.py would still apply it.
for _old in OUT.glob("*.patch"): _old.unlink()
man=json.loads((LOL/"upstream/manifest.json").read_text())
tot=0; rows=[]
for c in man["components"]:
    name="root" if c["path"]=="." else c["path"].replace("/","_")
    box=WORK/name
    if not box.exists(): continue
    # bytes, not text: capturing with text=True applies universal-newline translation and
    # silently strips the CRs out of any CRLF file's context lines, so the patch stops applying.
    d=subprocess.run(["git","-C",str(box),"diff","--binary","lolbase","HEAD","--",".",":(exclude).conflicts"],
                     capture_output=True).stdout
    if not d.strip(): continue
    d_is_bytes=True
    # Keep darling-lol's own placeholder convention: no absolute local paths in a patch.
    for tok,val in ((b"@HOST_HOME@",str(HOME).encode()),(b"@GUEST_USER@",b"jsabella")):
        d=d.replace(val,tok)
    f=OUT/pathlib.Path(c["patch"]).name
    f.write_bytes(d)
    n=len([l for l in d.splitlines() if l.startswith((b"+",b"-")) and not l.startswith((b"+++",b"---"))])
    rows.append((c["path"],f.name,n)); tot+=n
for p,f,n in rows: print("  %-34s %-24s %6d changed lines"%(p[:34],f,n))
print("\n%d patches, %d changed lines total"%(len(rows),tot))
leak=subprocess.run(["grep","-rl","/home/jsabella",str(OUT)],capture_output=True,text=True).stdout.split()
print("patches still containing an absolute home path:",leak or "none")
