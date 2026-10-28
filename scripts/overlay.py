#!/usr/bin/env python3
"""Apply the jsabella overlay (patches-jsabella/) on top of darling-lol's own patches.

Run this after scripts/prepare.py. darling-lol's patches in patches/ are left byte-identical
so `git pull upstream main` stays a normal merge; everything from this tree lives in the
second layer and can be re-generated against a newer upstream.

    python3 scripts/prepare.py
    python3 scripts/overlay.py            # or --check-only / --reverse
"""
import argparse, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, render

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, default=ROOT / 'build/darling-src')
p.add_argument('--check-only', action='store_true', help='verify each patch applies; change nothing')
p.add_argument('--reverse', action='store_true', help='remove the overlay again')
a = p.parse_args()

source = a.source.resolve()
manifest = json.loads((ROOT / 'upstream/manifest.json').read_text())
layer = ROOT / 'patches-jsabella'

def applies(repo, patch, reverse=False):
    return subprocess.run(['git', '-C', str(repo), 'apply', *(['--reverse'] if reverse else []),
                           '--check', '-'], input=patch, text=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

done = skipped = 0
for component in manifest['components']:
    patch_file = layer / Path(component['patch']).name
    if not patch_file.exists():
        continue
    repo = source if component['path'] == '.' else source / component['path']
    if not repo.exists():
        raise SystemExit('%s is missing; run scripts/prepare.py first' % repo)
    patch = render(patch_file.read_text())

    if a.reverse:
        if applies(repo, patch, reverse=True):
            subprocess.run(['git', '-C', str(repo), 'apply', '--reverse', '--whitespace=nowarn',
                            '-'], input=patch, text=True, check=True)
            print('Removed  ' + component['path'], flush=True)
            done += 1
        else:
            print('Absent   ' + component['path'], flush=True); skipped += 1
        continue

    # Already applied reads as "the reverse applies", which is success, not an error.
    if applies(repo, patch, reverse=True):
        print('Already  ' + component['path'], flush=True); skipped += 1
        continue
    if not applies(repo, patch):
        raise SystemExit('%s: patches-jsabella/%s does not apply to the prepared source. '
                         'The upstream patch under it has probably moved; regenerate the '
                         'overlay (see MERGE-NOTES.md).' % (component['path'], patch_file.name))
    if not a.check_only:
        subprocess.run(['git', '-C', str(repo), 'apply', '--whitespace=nowarn', '-'],
                       input=patch, text=True, check=True)
    print(('Checked  ' if a.check_only else 'Applied  ') + component['path'], flush=True)
    done += 1

print('\n%d component%s %s, %d skipped' %
      (done, '' if done == 1 else 's',
       'checked' if a.check_only else ('reversed' if a.reverse else 'patched'), skipped))
