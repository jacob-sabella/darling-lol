#!/usr/bin/env python3
"""List the dylibs a Mach-O loads, marking weak links. Reads load commands only."""
import struct, sys, os

LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB = 0x0c, 0x18, 0x1f
MAGICS = {0xfeedface: ('<', 4), 0xfeedfacf: ('<', 8),
          0xcefaedfe: ('>', 4), 0xcffaedfe: ('>', 8)}


def slices(data):
    magic = struct.unpack('>I', data[:4])[0]
    if magic in (0xcafebabe, 0xbebafeca):  # fat
        n = struct.unpack('>I', data[4:8])[0]
        for i in range(n):
            off = struct.unpack('>I', data[8 + i * 20 + 8: 8 + i * 20 + 12])[0]
            yield off
    else:
        yield 0


def deps(path):
    with open(path, 'rb') as handle:
        data = handle.read(64)
        if len(data) < 8:
            return
        handle.seek(0)
        head = handle.read(4096)
        for base in slices(head):
            handle.seek(base)
            header = handle.read(32)
            magic = struct.unpack('<I', header[:4])[0]
            if magic not in MAGICS:
                continue
            endian, width = MAGICS[magic]
            ncmds = struct.unpack(endian + 'I', header[16:20])[0]
            sizeofcmds = struct.unpack(endian + 'I', header[20:24])[0]
            handle.seek(base + (32 if width == 8 else 28))
            commands = handle.read(sizeofcmds)
            offset = 0
            for _ in range(ncmds):
                if offset + 8 > len(commands):
                    break
                cmd, size = struct.unpack(endian + 'II', commands[offset:offset + 8])
                if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB):
                    name_off = struct.unpack(endian + 'I', commands[offset + 8:offset + 12])[0]
                    raw = commands[offset + name_off: offset + size]
                    name = raw.split(b'\0', 1)[0].decode('utf-8', 'replace')
                    yield name, (cmd == LC_LOAD_WEAK_DYLIB)
                offset += size
            return  # one slice is enough


for target in sys.argv[1:]:
    try:
        for name, weak in deps(target):
            print(('weak' if weak else 'hard'), name, sep='\t')
    except (OSError, struct.error):
        pass
