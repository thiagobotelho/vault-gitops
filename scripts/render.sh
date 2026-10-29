#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
readarray -t LOCK < <(python3 - "$ROOT" <<'PYLOCK'
import pathlib,sys,yaml
x=yaml.safe_load((pathlib.Path(sys.argv[1])/'helm/chart.lock.yaml').read_text())
for k in ['repository','version','sha256']:print(x[k])
PYLOCK
)
helm pull vault --repo "${LOCK[0]}" --version "${LOCK[1]}" --destination "$TMP"
printf '%s  %s\n' "${LOCK[2]}" "$TMP/vault-${LOCK[1]}.tgz" | sha256sum --check
helm template vault "$TMP/vault-${LOCK[1]}.tgz" --namespace vault --skip-tests -f "$ROOT/helm/values-crc.yaml" | sed -E 's/[[:blank:]]+$//' > "$TMP/rendered.yaml"
if [[ ${1:-} == --check ]]; then
  diff -u "$ROOT/base/vault-rendered.yaml" "$TMP/rendered.yaml"
else
  cp "$TMP/rendered.yaml" "$ROOT/base/vault-rendered.yaml"
fi
