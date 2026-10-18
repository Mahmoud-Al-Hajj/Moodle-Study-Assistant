"""Write the API schema to web/src/api/openapi.json (then: cd web; npm run gen:api).

    .venv\\Scripts\\python -m api.export_openapi
"""

import json

from .main import ROOT, app

OUT = ROOT / "web" / "src" / "api" / "openapi.json"


def schema_text() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(schema_text(), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
