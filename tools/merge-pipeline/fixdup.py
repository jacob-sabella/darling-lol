"""Delete the duplicate declarations clang itself points at.

Both trees filled the same Cocotron/CoreMedia gaps. When the two additions land
at different points in a file git merges them as text with no conflict, and the
result declares one thing twice. Guessing at those duplicates with regexes is
unreliable -- a trailing comment or a two-line method signature defeats the
pattern, and a half-deleted declaration is worse than the duplicate. clang
already reports each one exactly, with the redefinition site and a note pointing
at the copy to keep, so the diagnostics drive the edit.

Edits are applied to the merge boxes (so they reach the generated patches) and to
the prepared build tree (so the next make picks them up without re-preparing).
"""
import json, pathlib, re, subprocess, sys, collections

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE / "merge"
LOL = pathlib.Path.home() / "Projects/darling-lol"
SRC = LOL / "build/darling-src"
man = json.loads((LOL / "upstream/manifest.json").read_text())

# longest component path first, so src/external/foundation wins over "."
COMPONENTS = sorted(((c["path"], c["path"].replace("/", "_") if c["path"] != "." else "root")
                     for c in man["components"]), key=lambda t: -len(t[0]))

DUP = re.compile(
    r"^(?P<file>/[^:]+):(?P<line>\d+):(?P<col>\d+): error: "
    r"(?:redefinition of enumerator '(?P<enum>[^']+)'"
    r"|redefinition of '(?P<sym>[^']+)'"
    r"|typedef redefinition with different types"
    r"|duplicate member '(?P<mem>[^']+)'"
    r"|duplicate declaration of method '(?P<meth>[^']+)')", re.M)


def box_for(abs_path):
    """Map a path in the build tree back to its merge box and in-box path."""
    try:
        rel = pathlib.Path(abs_path).resolve().relative_to(SRC.resolve())
    except Exception:
        return None, None
    s = str(rel)
    for cpath, boxname in COMPONENTS:
        if cpath == ".":
            return boxname, s
        if s.startswith(cpath + "/"):
            return boxname, s[len(cpath) + 1:]
    return None, None


SCOPE = re.compile(r"^\s*@(interface|implementation|protocol|end)\b")


def extent(lines, i, is_enumerator):
    """Lines [a,b] holding the declaration clang pointed at on line i.

    Only an enumerator expands backwards, and only as far as its own enum block:
    deleting one name out of an enum leaves its siblings behind, and clang reports
    those one build at a time. A duplicate ivar, typedef, variable or method
    declaration is exactly the statement at that line -- expanding it backwards
    walks out to the enclosing '@interface ... {' and deletes the whole class."""
    a = i
    if is_enumerator:
        depth = 0
        for k in range(i, -1, -1):
            if SCOPE.match(lines[k]):        # never cross a class/protocol boundary
                break
            depth += lines[k].count("}") - lines[k].count("{")
            if depth < 0:                    # the unclosed '{' that encloses us
                a = k
                break
    # forward to this statement's terminator
    depth, b = 0, a
    for k in range(a, len(lines)):
        depth += lines[k].count("{") - lines[k].count("}")
        b = k
        if depth <= 0 and ";" in lines[k].split("//")[0]:
            break
    return a, b


def main(*logpaths):
    text = "\n".join(pathlib.Path(p).read_text(errors="replace") for p in logpaths)
    hits = collections.defaultdict(set)      # (box, relpath) -> {line numbers}
    seen = []
    for m in DUP.finditer(text):
        f, ln = m.group("file"), int(m.group("line"))
        sym = (m.group("enum") or m.group("sym") or m.group("mem")
               or m.group("meth") or "typedef")
        box, rel = box_for(f)
        if not box:
            seen.append(("UNMAPPED", f, ln, sym)); continue
        hits[(box, rel)].add((ln, m.group("enum") is not None, sym))
        seen.append((box, rel, ln, sym))

    if not hits:
        print("no duplicate-declaration diagnostics in", ", ".join(logpaths))
        return 0

    print("%-24s %-44s %6s  %s" % ("component", "file", "line", "symbol"))
    for b, f, ln, s in seen:
        print("%-24s %-44s %6s  %s" % (str(b)[:24], str(f)[-44:], ln, s))

    total = 0
    for (box, rel), lns in sorted(hits.items()):
        bp = WORK / box / rel
        sp = SRC / rel if box == "root" else None
        if sp is None:
            cpath = next(c for c, bn in COMPONENTS if bn == box)
            sp = SRC / cpath / rel
        if not bp.exists():
            print("  !! no merge-box file:", bp); continue
        lines = bp.read_text(errors="replace").splitlines(True)
        # resolve each diagnostic to a line range, then delete from the bottom up
        # A log can be replayed after the file changed, in which case its line
        # numbers point somewhere else entirely. Only delete a range that really
        # does contain the symbol clang named there.
        ranges = []
        for ln, is_en, sym in sorted(lns):
            if ln - 1 >= len(lines):
                print("  stale (past EOF) %-40s line %d" % (rel[-40:], ln)); continue
            a, b = extent(lines, ln - 1, is_en)
            if sym != "typedef" and sym not in "".join(lines[a:b + 1]):
                print("  stale (%s not at line %d) %s" % (sym, ln, rel[-40:])); continue
            ranges.append((a, b))
        if not ranges:
            continue
        merged = []
        for a, b in sorted(set(ranges), reverse=True):
            # merge only genuine overlaps. Adjacent ranges must stay separate:
            # merging them swallows the untouched lines in between, which is how
            # three CoreMedia constants that were never duplicated got deleted.
            if merged and b >= merged[-1][0]:
                merged[-1] = (min(a, merged[-1][0]), max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        unsafe = [(a, b) for a, b in merged
                  if any(SCOPE.match(lines[k]) for k in range(a, b + 1))]
        if unsafe:
            print("  !! %s: computed extent crosses a class boundary at %s -- skipped"
                  % (rel, unsafe))
            continue
        for a, b in merged:
            del lines[a:b + 1]
            total += 1
        out = "".join(lines)
        bp.write_text(out)
        if sp.exists():
            sp.write_text(out)                 # keep the build tree in step
        print("  %-26s %-50s removed %d block(s)" % (box[:26], rel[-50:], len(merged)))
    print("removed %d duplicate declaration block(s) in %d file(s)" % (total, len(hits)))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
