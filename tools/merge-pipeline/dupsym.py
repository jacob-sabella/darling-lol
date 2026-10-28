"""Resolve the definitions that ld reported as duplicate.

These never conflicted textually: each side added the same symbol to a DIFFERENT
file, so both copies survived the merge untouched and only the linker objected.
One copy has to go, and which one is a judgement about the two implementations,
not something a merge rule can decide -- so each is recorded here with its reason.
"""
import pathlib, subprocess

WORK = pathlib.Path(__file__).resolve().parent / "merge"


def cut(box, path, text, why, expect=1):
    p = WORK / box / path
    if not p.exists():
        print("  MISSING %s/%s" % (box, path)); return
    s = p.read_text(errors="replace")
    n = s.count(text)
    if n == 0:
        print("  already gone   %-46s" % path[-46:]); return
    if n != expect:
        print("  !! %s: anchor found %d time(s), expected %d -- skipped"
              % (path, n, expect)); return
    p.write_text(s.replace(text, "", 1))
    print("  %-46s %s" % (path.split("/")[-1], why))


# HIToolbox: theirs is a file of four stubs that return -4; mine implements all
# four for real (CFString-keyed property storage, a refcounted secure-input mode).
# The whole file is redundant, so it leaves the build with its CMake entry.
cut("root", "src/frameworks/Carbon/HIToolbox/CMakeLists.txt",
    "\t\tsrc/SecureInput.c\n",
    "drop their stub file; mine implements all four for real")
sec = WORK / "root/src/frameworks/Carbon/HIToolbox/src/SecureInput.c"
if sec.exists():
    sec.unlink()
    subprocess.run(["git", "-C", str(WORK / "root"), "rm", "-q", "-f", "--ignore-unmatch",
                    "--", "src/frameworks/Carbon/HIToolbox/src/SecureInput.c"])

# CoreLocation: both sides defined the six accuracy constants, with identical
# values. Theirs live in a file of their own (CLLocation.m), which is the better
# home, so mine go.
cut("root", "src/frameworks/CoreLocation/src/CoreLocation.m",
    """const CLLocationAccuracy kCLLocationAccuracyBestForNavigation = -2.0;
const CLLocationAccuracy kCLLocationAccuracyBest = -1.0;
const CLLocationAccuracy kCLLocationAccuracyNearestTenMeters = 10.0;
const CLLocationAccuracy kCLLocationAccuracyHundredMeters = 100.0;
const CLLocationAccuracy kCLLocationAccuracyKilometer = 1000.0;
const CLLocationAccuracy kCLLocationAccuracyThreeKilometers = 3000.0;
""",
    "identical values; theirs kept in CLLocation.m")

# ImageCaptureCore: the values differ. Apple's transport-type constants carry
# their own name as their value, and this one is a transport type, not a download
# option, so theirs is wrong twice over.
cut("root", "src/frameworks/ImageCaptureCore/src/ICCameraItem.m",
    'ICDownloadOption const ICTransportTypeMassStorage = @"MassStorage";\n',
    "wrong value and wrong type; mine kept in ICDevice.m")

# LaunchServices: both are stubs. Theirs returns noErr because a client
# registering a URL scheme only needs the call to succeed; mine returns
# kLSCannotSetInfoErr, which is more faithful but can surface as an error to the
# very client this tree exists to run. Theirs is the pragmatic one.
cut("root", "src/frameworks/CoreServices/src/LaunchServices/LSInfo.m",
    """OSStatus LSSetDefaultHandlerForURLScheme(CFStringRef inURLScheme, CFStringRef inHandlerBundleID)
{
	puts("LSSetDefaultHandlerForURLScheme STUB");
	return kLSCannotSetInfoErr;
}

OSStatus LSSetDefaultRoleHandlerForContentType(CFStringRef inContentType, LSRolesMask inRole, CFStringRef inHandlerBundleID)
{
	puts("LSSetDefaultRoleHandlerForContentType STUB");
	return kLSCannotSetInfoErr;
}
""",
    "theirs returns noErr, which the client needs")

# CoreText: the values differ, and CoreText's collection option keys are the
# older NSFontCollection names on macOS, which is what mine uses.
cut("src_external_cocotron", "CoreText/CTFontDescriptor.m",
    'const CFStringRef kCTFontCollectionRemoveDuplicatesOption = CFSTR("kCTFontCollectionRemoveDuplicatesOption");\n',
    "mine kept in constants.c (NSFontCollection name)")
