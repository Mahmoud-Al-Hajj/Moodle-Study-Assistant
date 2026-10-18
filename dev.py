"""Start the web UI for development: the API and the web app, with live reload.

    .\\dev                (dev.bat: same as .venv\\Scripts\\python dev.py)
    .\\dev --no-open      don't open the browser

API: http://127.0.0.1:8765 (only reachable from this computer). App: http://127.0.0.1:5173
Ctrl+C stops both.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from api.jobs import kill_tree

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
API_PORT, WEB_PORT = 8765, 5173
APP_URL = f"http://127.0.0.1:{WEB_PORT}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the API and the web app for development.")
    parser.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    npm = shutil.which("npm")
    if not npm:
        print("Node.js isn't installed (npm not found). Install the LTS version from https://nodejs.org")
        return 1
    if not (WEB / "node_modules").exists():
        print("The web app's packages aren't installed yet. Run once:\n    cd web\n    npm install")
        return 1

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
    # The API listens on 127.0.0.1 only: never 0.0.0.0, so nothing outside this computer can reach it.
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1",
                            "--port", str(API_PORT), "--reload", "--reload-dir", "api"], cwd=ROOT, env=env, **flags)
    web = subprocess.Popen([npm, "run", "dev"], cwd=WEB, env=env, **flags)
    print(f"\nStarting... the app will be at {APP_URL}  (Ctrl+C to stop)\n")
    try:
        if not args.no_open:
            time.sleep(3)
            webbrowser.open(APP_URL)
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
        print("One of the servers stopped; shutting down the other.")
        return 1
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for proc in (api, web):
            kill_tree(proc)


if __name__ == "__main__":
    sys.exit(main())
