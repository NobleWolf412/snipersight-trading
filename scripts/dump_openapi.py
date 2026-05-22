"""Dump FastAPI's OpenAPI schema to build/openapi.json for TS-type generation.

Used by `npm run gen:types` (CLAUDE.md §20 frontend<->backend contract validation).
The output is consumed by `openapi-typescript` to produce src/types/api.ts.

build/ is gitignored — only src/types/api.ts gets committed. The openapi.json itself
is a transient build artifact, regenerated on every gen:types invocation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# When invoked as `python scripts/dump_openapi.py`, Python puts scripts/ on sys.path
# but NOT the repo root — so `import backend.*` fails. Prepend repo root explicitly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    try:
        from backend.api_server import app  # type: ignore
    except Exception as exc:
        print(f"[dump_openapi] failed to import backend.api_server: {exc!r}", file=sys.stderr)
        return 1

    out = Path("build/openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"[dump_openapi] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
