import pathlib
p=pathlib.Path("/tmp/claude-1000/-home-jsabella-Projects-darling/46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge/src_external_cocotron/AppKit/NSAccessibilityRemoteUIElement.m")
t=p.read_text(); a="- (id) initWithRemoteToken: (NSData *) remoteToken {"
g='''/* Kept from darling-lol: without an -init of its own, a plain
   [[NSAccessibilityRemoteUIElement alloc] init] falls through to
   -forwardInvocation:, whose "v@:" signature leaves the return buffer
   uninitialized, and Chromium's RemoteAccessibility took that garbage
   pointer as the new object and crashed shortly after. */
- (id) init {
    return [super init];
}

'''
if "- (id) init {" in t: print("  graft: already present")
else:
    assert a in t; p.write_text(t.replace(a,g+a,1)); print("  grafted darling-lol's -init")
