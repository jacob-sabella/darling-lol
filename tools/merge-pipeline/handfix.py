"""Fixes a real build found that no textual merge or symbol audit can see.

Each is one feature implemented twice, where the duplicate is a C declaration, an entry in a
code generator's call list, or a struct field -- none of which a line- or selector-level
audit catches, and all of which only a compiler reports.
"""
import pathlib
WORKDIR = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                       "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge")
R = pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/"
                 "46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge/src_external_darlingserver")
EDITS = [
 ("duct-tape/include/darlingserver/duct-tape.h",
  """
// Wraps a descriptor the server holds in a port the caller can send, and
// unwraps one again. The descriptor handed back is the server's to dup out.
uint32_t dtape_fileport_makeport(int fd);
int dtape_fileport_makefd(uint32_t port_name);
""", "\n",
  "fileport.c is darling-lol's task-scoped implementation, so its declarations are the "
  "ones with a definition behind them"),
 ("scripts/generate-rpc-wrappers.py",
  """
	# Wraps a descriptor in a port the caller can hand to another task, and
	# unwraps one again on the receiving side.
	('fileport_makeport', [
		('fd', '@fd'),
	], [
		('port_name', 'uint32_t'),
	]),

	('fileport_makefd', [
		('port_name', 'uint32_t'),
	], [
		('fd', '@fd'),
	]),
""", "",
  "both trees appended the same two RPC calls, so the generated rpc.h declared each twice "
  "and gave them two different call numbers"),
 ("duct-tape/xnu/osfmk/vm/vm_map.h",
  """	/* darling-lol: duct-tape shared backing. XNU's object model is not
	 * wired up here; instead an entry may carry a shared memfd descriptor
	 * (see dtape_map_shared_descriptor in duct-tape/src/memory.c) that is
	 * mapped into tasks on demand, giving true cross-task sharing.
	 * Opaque pointer to avoid header coupling; NULL when unused. */
	void                    *dtape_descriptor;
""", "",
  "duct-tape/src/memory.c here is ours and uses the typed descriptor plus "
  "dtape_page_offset, so their opaque duplicate of the field goes"),
]
for rel, old, new, why in EDITS:
    p = R / rel
    t = p.read_text()
    if old not in t:
        print("  SKIP (already applied?) %s" % rel); continue
    p.write_text(t.replace(old, new, 1))
    print("  %-52s %s" % (rel[-52:], why[:60]))


# ---------------------------------------------------------------------------
# Two grafts in darlingserver, where the coupled-group pass took one side's file
# and the other side's change to the same code has to come along with it.
DS = R


def graft_in(box, path, old, new, why):
    p = WORKDIR / box / path
    if not p.exists():
        print("  MISSING", path); return
    t = p.read_text()
    if new in t:
        print("  already grafted", path); return
    if t.count(old) != 1:
        print("  !! %s: anchor appears %d time(s), not grafting" % (path, t.count(old))); return
    p.write_text(t.replace(old, new))
    print("  %-22s %s" % (path.split("/")[-1], why))


def graft(path, old, new, why):
    p = DS / path
    if not p.exists():
        print("  MISSING", path); return
    t = p.read_text()
    if new in t:
        print("  already grafted", path); return
    if t.count(old) != 1:
        print("  !! %s: anchor appears %d time(s), not grafting" % (path, t.count(old))); return
    p.write_text(t.replace(old, new))
    print("  %-22s %s" % (path.split("/")[-1], why))


# call.cpp is darling-lol's (it has to agree with their fileport arity), but
# notifyCheckin's second parameter is mine: every thread checks in, and only the
# main thread's checkin means the process itself has arrived, so only that one may
# wake a parent waiting in fork_wait_for_child.
graft("src/call.cpp",
      "process->notifyCheckin(static_cast<Process::Architecture>(_header.architecture));",
      "process->notifyCheckin(static_cast<Process::Architecture>(_header.architecture), "
      "thread->nsid());",
      "pass the checking-in thread's nsid")

# Both trees widened the same undeliverable-message test in sendMany, to different
# errnos: mine added ECONNRESET/ENOTCONN (an addressless datagram on an unconnected
# socket), theirs added ENOENT. Whichever file wins, the union is what is correct --
# every one of these means the message can never be delivered.
graft("src/message.cpp",
      "} else if (errno == EPIPE || errno == ECONNREFUSED || errno == ENOENT) {",
      "} else if (errno == EPIPE || errno == ECONNREFUSED || errno == ENOENT "
      "|| errno == ECONNRESET || errno == ENOTCONN) {",
      "re-apply my ECONNRESET/ENOTCONN onto their file")


# Their NSResponder.h declared the three otherMouse* methods and their
# NSResponder.m defines them; mine's header, which wins above for its typed
# touch-bar API, never declared them. Without these, any caller of
# -otherMouseDown: sees no visible declaration.
graft_in("src_external_cocotron", "AppKit/include/AppKit/NSResponder.h",
         """- (void) rightMouseUp: (NSEvent *) event;""",
         """- (void) otherMouseDown: (NSEvent *) event;
- (void) otherMouseUp: (NSEvent *) event;
- (void) otherMouseDragged: (NSEvent *) event;
- (void) rightMouseUp: (NSEvent *) event;""",
         "re-declare their otherMouse* methods")
