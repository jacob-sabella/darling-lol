#!/usr/bin/env python3
"""Three-way merge: pinned revision -> {darling-lol patch, jsabella working tree}.

Every darling-lol pin equals the HEAD of the matching repo in ~/Projects/darling, so the
pinned revision is a genuine common ancestor and this is a real merge, not a rebase.

The user's working trees are never touched: each component is cloned --shared read-only.
"""
import json, os, pathlib, shutil, subprocess, sys

HOME = pathlib.Path.home()
LOL  = HOME / "Projects/darling-lol"
U    = HOME / "Projects/darling"
WORK = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                    "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")

# Riot's installer app and the game zip are not ours to redistribute, and upstream ships no
# game files. The .orig is a patch backup, not source. The progress log is kept out of the
# component patches (it is full of absolute local paths) and handled separately.
EXCLUDE_PREFIX = ("lol_installer/", "Install League of Legends na.zip", ".lol-progress.md",
                  # Our only change to this linker export list is an accidental CRLF->LF
                  # conversion. Keep darling-lol's bytes.
                  "src/frameworks/CoreServices/reexport.exp")
EXCLUDE_SUFFIX = (".orig", ".rej", ".bak", ".bak-claude")


def sh(cmd, cwd=None, check=True, inp=None):
    r = subprocess.run(cmd, cwd=cwd and str(cwd), capture_output=True, text=True, input=inp)
    if check and r.returncode:
        raise RuntimeError("%s\n%s%s" % (" ".join(map(str, cmd)), r.stdout[-3000:], r.stderr[-3000:]))
    return r.returncode, r.stdout + r.stderr


def status(p):
    out = sh(["git", "-C", str(p), "status", "--porcelain", "-z", "--untracked-files=all"])[1]
    items = []
    for e in out.split("\0"):
        if len(e) > 3:
            items.append((e[:2], e[3:]))
    return items


def wanted(f, src):
    # A submodule gitlink shows up as a modified path in the superproject. Each submodule is
    # its own manifest component, so skip directories here.
    if (src / f).is_dir():
        return False
    return not (f.startswith(EXCLUDE_PREFIX) or f.endswith(EXCLUDE_SUFFIX))


def main():
    man = json.loads((LOL / "upstream/manifest.json").read_text())
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    report = []

    for c in man["components"]:
        cpath, pin = c["path"], c["revision"]
        src = U if cpath == "." else U / cpath
        st = [(s, f) for s, f in status(src)]
        mine_mod = [f for s, f in st if s.strip() in ("M", "MM", "AM") and wanted(f, src)]
        mine_del = [f for s, f in st if s.strip() == "D" and wanted(f, src)]
        mine_new = [f for s, f in st if s == "??" and wanted(f, src)]
        if not (mine_mod or mine_del or mine_new):
            continue

        name = "root" if cpath == "." else cpath.replace("/", "_")
        box = WORK / name
        sh(["git", "clone", "--shared", "--no-checkout", "-q", str(src), str(box)])
        sh(["git", "-C", str(box), "config", "user.email", "jacobsabella@outlook.com"])
        sh(["git", "-C", str(box), "config", "user.name", "Jacob Sabella"])
        # zdiff3 keeps the common ancestor's lines in the markers, so a conflict where both
        # sides only ADDED (empty base) can be told apart from one where both REWROTE the
        # same lines. The first is safe to combine; the second needs a decision.
        sh(["git", "-C", str(box), "config", "merge.conflictStyle", "zdiff3"])
        sh(["git", "-C", str(box), "checkout", "--detach", "-q", pin])
        sh(["git", "-C", str(box), "switch", "-c", "base", "-q"])

        # --- side A: darling-lol's patch, applied raw so @TOKEN@ placeholders survive
        sh(["git", "-C", str(box), "switch", "-c", "lol", "-q"])
        patch = (LOL / c["patch"]).read_text()
        rc, out = sh(["git", "-C", str(box), "apply", "--whitespace=nowarn", "-"],
                     check=False, inp=patch)
        if rc:
            report.append((cpath, "LOL-PATCH-FAILED", out[-300:], 0, 0))
            continue
        sh(["git", "-C", str(box), "add", "-A"])
        sh(["git", "-C", str(box), "commit", "-q", "-m", "darling-lol " + c["patch"]])
        # Tag it NOW. The merge runs on this branch and git auto-commits a clean merge, so
        # `lol` stops meaning "their patch alone" the moment that happens -- and comparing
        # the merge against itself made every audit blind on cleanly-merged components.
        sh(["git", "-C", str(box), "tag", "-f", "lolbase", "HEAD"])

        # --- side B: jsabella's working tree
        sh(["git", "-C", str(box), "switch", "base", "-q"])
        sh(["git", "-C", str(box), "switch", "-c", "mine", "-q"])
        for f in mine_mod + mine_new:
            d = box / f
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / f, d)
        for f in mine_del:
            (box / f).unlink(missing_ok=True)
        sh(["git", "-C", str(box), "add", "-A"])
        sh(["git", "-C", str(box), "commit", "-q", "-m", "jsabella working tree"])

        # --- merge
        sh(["git", "-C", str(box), "switch", "lol", "-q"])
        rc, out = sh(["git", "-C", str(box), "merge", "--no-edit", "-m", "merge jsabella", "mine"],
                     check=False)
        conf = sh(["git", "-C", str(box), "diff", "--name-only", "--diff-filter=U"])[1].split()
        report.append((cpath, "CLEAN" if rc == 0 else "CONFLICT",
                       "", len(mine_mod) + len(mine_new) + len(mine_del), len(conf)))
        (box / ".conflicts").write_text("\n".join(conf))

    print("%-34s %-20s %6s %9s" % ("component", "result", "yours", "conflicts"))
    print("-" * 74)
    tc = tf = 0
    for cpath, res, note, nmine, nconf in report:
        print("%-34s %-20s %6d %9d %s" % (cpath[:34], res, nmine, nconf, note))
        tc += nconf; tf += nmine
    print("-" * 74)
    print("%d of your files, %d conflicted paths" % (tf, tc))


if __name__ == "__main__":
    main()
