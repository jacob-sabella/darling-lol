r"""Fix my CoreServices re-export generation for a 64-bit-only build.

My change appends the NSUserActivity class symbols to the re-export list it reads
from reexport.exp. That file's last line, _remquo$fenv_access_off, has no trailing
newline, so the first appended symbol was concatenated onto it and the link failed
on _remquo$fenv_access_off_OBJC_CLASS_$_NSUserActivity -- a symbol that is really
two. It also wrote and passed the 32-bit list unconditionally, and darling-lol
configures with TARGET_i386=OFF, so ld was handed an export list for a slice this
build does not produce (with an empty -Xarch_ in front of it).
"""
import pathlib

F = (pathlib.Path(__file__).resolve().parent
     / "merge/root/src/frameworks/CoreServices/CMakeLists.txt")

OLD = r"""file(READ ${CMAKE_CURRENT_SOURCE_DIR}/reexport.exp CoreServices_reexports)
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_64BIT}.exp
	"${CoreServices_reexports}_OBJC_CLASS_$_NSUserActivity\n_OBJC_METACLASS_$_NSUserActivity\n")
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_32BIT}.exp
	"${CoreServices_reexports}.objc_class_name_NSUserActivity\n")

set_property(TARGET CoreServices APPEND_STRING PROPERTY LINK_FLAGS
  " -Xarch_${APPLE_ARCH_64BIT} -Wl,-reexported_symbols_list,${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_64BIT}.exp")
set_property(TARGET CoreServices APPEND_STRING PROPERTY LINK_FLAGS
  " -Xarch_${APPLE_ARCH_32BIT} -Wl,-reexported_symbols_list,${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_32BIT}.exp")"""

NEW = r"""file(READ ${CMAKE_CURRENT_SOURCE_DIR}/reexport.exp CoreServices_reexports)
# reexport.exp has no trailing newline, so strip and re-add one: without it the
# first symbol appended below is concatenated onto its last line.
string(STRIP "${CoreServices_reexports}" CoreServices_reexports)

if (TARGET_x86_64)
	file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_64BIT}.exp
		"${CoreServices_reexports}\n_OBJC_CLASS_$_NSUserActivity\n_OBJC_METACLASS_$_NSUserActivity\n")
	set_property(TARGET CoreServices APPEND_STRING PROPERTY LINK_FLAGS
		" -Xarch_${APPLE_ARCH_64BIT} -Wl,-reexported_symbols_list,${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_64BIT}.exp")
endif ()

if (TARGET_i386)
	file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_32BIT}.exp
		"${CoreServices_reexports}\n.objc_class_name_NSUserActivity\n")
	set_property(TARGET CoreServices APPEND_STRING PROPERTY LINK_FLAGS
		" -Xarch_${APPLE_ARCH_32BIT} -Wl,-reexported_symbols_list,${CMAKE_CURRENT_BINARY_DIR}/reexport-${APPLE_ARCH_32BIT}.exp")
endif ()"""

t = F.read_text()
if NEW in t:
    print("  CoreServices re-export fix already present")
elif t.count(OLD) == 1:
    F.write_text(t.replace(OLD, NEW))
    print("  CoreServices/CMakeLists.txt  newline before the appended symbol; "
          "each list only for a slice being built")
else:
    print("  !! CoreServices anchor found %d time(s), expected 1 -- not patched"
          % t.count(OLD))
