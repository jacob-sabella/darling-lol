set -e
cd /tmp/claude-1000/-home-jsabella-Projects-darling/46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad
python3 -I merge.py >/dev/null 2>&1
python3 -I resolve_all.py 2>&1 | grep -E 'union|coupled-group|^\{|total resolved'
python3 -I graft.py
python3 -I handfix.py
python3 -I coreservices.py
python3 -I dupsym.py
python3 -I dedupe.py  2>&1 | tail -1
python3 -I dedupe2.py 2>&1 | tail -1
# replay the duplicate declarations clang reported, so the fix survives a re-run
python3 -I fixdup.py duplicate-diagnostics.log 2>&1 | tail -5
python3 -I audit.py | head -1; python3 -I bal.py; python3 -I audit2.py | head -1
