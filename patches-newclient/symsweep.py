#!/usr/bin/env python3
"""Report every non-weak symbol the Riot client imports that the Darling runtime
does not define, so one run names all the dyld aborts instead of one per launch.

Two-level namespace imports say which dylib each symbol must come from, so the
check is per-library rather than against one flat pile. Re-exports are followed
transitively: Foundation's symbols legitimately arrive through Cocoa, and most of
libSystem's through its sub-libraries.
"""
import re
import subprocess
import sys
from pathlib import Path

RUNTIME = Path.home() / '.local/darling-lol/libexec/darling'
NM = ['llvm-nm', '--arch=x86_64']
UNDEF = re.compile(r'^\s*\(undefined\)\s+(weak\s+)?external\s+(\S+)(?:\s+\(from (\S+)\))?')

defined_cache: dict[Path, set[str]] = {}
reexport_cache: dict[Path, list[str]] = {}


def guest_path(install_name: str) -> Path | None:
    """The host file backing a guest install name, or None when it is not installed."""
    if not install_name.startswith('/'):
        return None
    candidate = RUNTIME / install_name.lstrip('/')
    return candidate if candidate.exists() else None


def dylib_commands(path: Path) -> list[tuple[str, bool]]:
    """(install name, is_reexport) for every dylib this image loads."""
    if path in reexport_cache:
        return reexport_cache[path]
    result = subprocess.run(['llvm-objdump', '--macho', '--private-headers', str(path)],
                            capture_output=True, text=True, errors='replace')
    names, kind = [], None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith('cmd LC_'):
            command = stripped.split()[1]
            kind = command if command in ('LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB',
                                          'LC_REEXPORT_DYLIB') else None
        elif kind and stripped.startswith('name '):
            names.append((stripped.split()[1], kind == 'LC_REEXPORT_DYLIB'))
            kind = None
    reexport_cache[path] = names
    return names


def load_commands(path: Path) -> list[str]:
    """Install names this image re-exports."""
    return [name for name, reexport in dylib_commands(path) if reexport]


def defined(path: Path, seen: set[Path] | None = None) -> set[str]:
    """External symbols this image provides, following re-exports."""
    seen = seen if seen is not None else set()
    if path in seen:
        return set()
    seen.add(path)
    if path in defined_cache:
        symbols = set(defined_cache[path])
    else:
        result = subprocess.run(NM + ['--defined-only', '--extern-only', str(path)],
                                capture_output=True, text=True, errors='replace')
        symbols = {line.split()[-1] for line in result.stdout.splitlines() if line.split()}
        defined_cache[path] = set(symbols)
    for name in load_commands(path):
        target = guest_path(name)
        if target:
            symbols |= defined(target, seen)
    return symbols


missing: dict[str, set[str]] = {}
unresolved: set[str] = set()

for argument in sys.argv[1:]:
    binary = Path(argument)
    result = subprocess.run(NM + ['-m', str(binary)], capture_output=True, text=True,
                            errors='replace')
    for line in result.stdout.splitlines():
        match = UNDEF.match(line)
        if not match:
            continue
        weak, symbol, source = match.group(1), match.group(2), match.group(3)
        if weak or not source:
            continue
        # nm prints the leaf of the install name; match it against this image's
        # own dylib list (all of them, not only the re-exported ones).
        matches = [name for name, _ in dylib_commands(binary)
                   if name.rsplit('/', 1)[-1] == source or name.endswith('/' + source)]
        target = None
        for name in matches:
            target = guest_path(name)
            if target:
                break
        if target is None:
            unresolved.add(source)
            continue
        if symbol not in defined(target):
            missing.setdefault(source, set()).add(symbol)

for source in sorted(missing):
    print(f'{source}: {len(missing[source])} missing')
    for symbol in sorted(missing[source]):
        print('   ', symbol)
if unresolved:
    print('\nlibraries not installed (checked separately):', ', '.join(sorted(unresolved)))
