"""Build the console upload ZIP using an allowlist; never package the workspace."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUTPUT = ROOT / "deploy" / "gyproject-beanstalk.zip"
ROOT_FILES = (
    "Dockerfile", ".dockerignore", "manage.py", "gunicorn.conf.py", "requirements.lock.txt"
)


def sources():
    for name in ROOT_FILES:
        yield BACKEND / name, name
    for directory in ("config", "core", "docker"):
        for path in sorted((BACKEND / directory).rglob("*")):
            relative = path.relative_to(BACKEND)
            if path.is_symlink() or not path.is_file():
                continue
            if any(part.startswith(".") or part in {"__pycache__", "tests"} for part in relative.parts):
                continue
            # Application source/templates/assets only; never arbitrary data files.
            if path.suffix not in {".py", ".sh", ".html", ".css", ".js", ".svg"}:
                continue
            yield path, relative.as_posix()
    yield ROOT / "deploy/beanstalk/Dockerrun.aws.json", "Dockerrun.aws.json"
    yield (
        ROOT / "deploy/beanstalk/.platform/nginx/conf.d/uploads.conf",
        ".platform/nginx/conf.d/uploads.conf",
    )


def add_file(archive, source, target):
    """Write a Linux-compatible ZIP member with explicit safe permissions."""
    data = source.read_bytes().replace(b"\r\n", b"\n")
    mode = 0o755 if source.suffix == ".sh" else 0o644

    info = ZipInfo(target)
    info.create_system = 3  # Unix, so external_attr is interpreted as POSIX mode bits.
    info.external_attr = (mode & 0xFFFF) << 16
    archive.writestr(info, data, compress_type=ZIP_DEFLATED)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for source, target in sources():
            add_file(archive, source, target)
    print(f"Created {OUTPUT}")
    print("Upload this ZIP to the Docker on Amazon Linux 2023 Beanstalk platform.")


if __name__ == "__main__":
    main()
