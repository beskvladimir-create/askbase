#!/bin/sh
# Build the site and put it live, in one command.
#
# Run from the repository root: it is linked to the Vercel project and the
# project's root directory is "site". Deploying from inside site/ would make
# the root site/site and deploy nothing; deploying from an unlinked directory
# creates a second project, which has happened once already.
#
# Pushing to git does not deploy: Vercel's GitHub app does not see this private
# repository, so this script is the way the site goes live.
set -e
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here"

"$here/.venv/bin/python" scripts/make_images.py
"$here/.venv/bin/python" scripts/build_site.py
npx --yes vercel@latest deploy --prod --yes >/dev/null

for path in / /install/ /model-ranking/ /ru/ /ru/ustanovka/; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "https://askbase.besk.tech$path")
  printf "  %-18s %s\n" "$path" "$code"
  [ "$code" = "200" ] || { echo "выложено не всё"; exit 1; }
done
echo "https://askbase.besk.tech"
