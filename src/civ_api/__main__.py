"""Entry point: run the CI-V Explorer HTTPS REST API with uvicorn.

Usage::

    python -m civ_api                     # HTTPS with a self-signed dev cert
    python -m civ_api --http              # plain HTTP (dev only)
    CIV_CERT=/path.crt CIV_KEY=/path.key python -m civ_api

The default dev certificate is generated on first run into the OS temp dir
so the API is usable immediately without manual setup.
"""

from __future__ import annotations

import argparse
import os
import ssl
import tempfile
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="civ_api", description="Run the Icom CI-V Explorer API.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8443)
    p.add_argument("--http", action="store_true", help="Serve plain HTTP instead of HTTPS (dev only)")
    return p


def _ensure_dev_cert() -> tuple[Path, Path]:
    """Return (cert_path, key_path), generating a self-signed cert if needed."""
    cert_env = os.environ.get("CIV_CERT") or ""
    key_env = os.environ.get("CIV_KEY") or ""
    if cert_env and key_env:
        return Path(cert_env), Path(key_env)

    tmp = Path(tempfile.gettempdir()) / "civ-api-dev"
    tmp.mkdir(parents=True, exist_ok=True)
    cert_path = tmp / "dev.crt"
    key_path = tmp / "dev.key"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    import subprocess

    subj = "/CN=localhost"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "365",
            "-nodes",
            "-subj",
            subj,
        ],
        check=True,
        capture_output=True,
    )
    return cert_path, key_path


def main() -> None:
    args = _build_parser().parse_args()

    import uvicorn

    if args.http:
        uvicorn.run("civ_api.app:app", host=args.host, port=args.port, reload=False)
        return

    cert_path, key_path = _ensure_dev_cert()
    uvicorn.run(
        "civ_api.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        ssl_certfile=str(cert_path),
        ssl_keyfile=str(key_path),
    )


if __name__ == "__main__":
    main()