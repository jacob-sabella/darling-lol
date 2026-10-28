set -e
cd /tmp/claude-1000/-home-jsabella-Projects-darling/46b82a72-82a7-4ffb-a403-f0cc40c2ddf6/scratchpad/merge
for b in */; do
  b="${b%/}"
  lc=$(git -C "$b" log --all --format='%H %s' | awk '/darling-lol patches\//{print $1; exit}')
  git -C "$b" tag -f lolbase "$lc" >/dev/null 2>&1
  grep -qx '.conflicts' "$b/.git/info/exclude" 2>/dev/null || echo ".conflicts" >> "$b/.git/info/exclude"
  git -C "$b" rm -q --cached .conflicts >/dev/null 2>&1 || true
  git -C "$b" add -A >/dev/null
  git -C "$b" commit -q --no-verify -m "merge jsabella working tree into darling-lol" >/dev/null 2>&1 || true
done
cd ..
rm -f ~/Projects/darling-lol/patches-jsabella/*.patch
python3 -I genpatch.py 2>&1 | tail -2
python3 -I roundtrip.py 2>&1 | tail -1
