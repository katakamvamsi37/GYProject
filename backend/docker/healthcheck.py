"""Liveness only: database outages must not restart every web container."""

from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/health/", timeout=3) as response:
    if response.status != 200:
        raise SystemExit(1)
