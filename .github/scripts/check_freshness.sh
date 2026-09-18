#!/usr/bin/env bash
# Run a tool's freshness check, and when it fails report the difference as an
# annotation. The log of a public repository needs a login to read, the
# annotations do not, and a freshness failure is a difference between a
# committed file and what the tool produces now.
set +e

module="$1"
output=$(python -m "$module" --check 2>&1)
status=$?
printf '%s\n' "$output"
if [ "$status" -eq 0 ]; then
  exit 0
fi

# Rewrite the output so the difference is in git, then report it.
python -m "$module" >/dev/null 2>&1
echo "::error title=$module freshness check failed::$(printf '%s' "$output" | tr '\n' '|' | head -c 700)"
echo "::error title=$module changed files::$(git status --porcelain | tr '\n' ' ' | head -c 500)"
for file in $(git diff --name-only | head -4); do
  body=$(git --no-pager diff --unified=0 -- "$file" | head -c 1500 | tr '\n' '|')
  echo "::error title=$module diff $file::$body"
done
echo "::notice title=$module environment::python $(python -V 2>&1) pyyaml $(python -c 'import yaml; print(yaml.__version__)')"
exit 1
