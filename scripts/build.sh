#!/usr/bin/env bash
# Build dist/lambda.zip reproducibly: sorted entries, fixed timestamps, no caches.
# Same source -> same zip hash -> Terraform only redeploys when code really changes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p dist
python3 - <<'PY'
import zipfile
from pathlib import Path

src = Path("src")
files = sorted(p for p in (src / "incidentscribe").rglob("*")
               if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc"})
with zipfile.ZipFile("dist/lambda.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for p in files:
        info = zipfile.ZipInfo(str(p.relative_to(src)), date_time=(2020, 1, 1, 0, 0, 0))
        info.external_attr = 0o644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, p.read_bytes())
print(f"dist/lambda.zip: {len(files)} files")
PY
