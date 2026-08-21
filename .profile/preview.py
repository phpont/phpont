#!/usr/bin/env python3
"""Serve the generated Pages artifact locally through stdlib HTTP."""
from __future__ import annotations
import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="serve docs/ on 127.0.0.1")
    parser.add_argument("--open", action="store_true", help="open the local HTTP preview in the Windows default browser")
    parser.add_argument("--port", type=int, default=8000, help="local TCP port (default: 8000)")
    args = parser.parse_args()
    if not (DOCS / "index.html").is_file(): raise SystemExit("render the profile first; docs/index.html is missing")
    if not args.serve:
        print((DOCS / "index.html").resolve()); return 0
    url = f"http://127.0.0.1:{args.port}/"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(DOCS)))
    print(url, flush=True)
    if args.open:
        if os.name != "nt": raise SystemExit("--open is supported only on Windows; open the printed URL manually.")
        os.startfile(url)  # type: ignore[attr-defined]
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0

if __name__ == "__main__": raise SystemExit(main())
