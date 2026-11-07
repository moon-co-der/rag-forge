"""Safe, bounded extraction of ZIP repository snapshots."""

import hashlib
import stat
import zipfile
from pathlib import Path, PurePosixPath

from ragforge.ingestion.models import RepositoryInfo, RepoSnapshot

MAX_ARCHIVE_ENTRIES = 5_000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000
_COPY_CHUNK_SIZE = 1024 * 1024


def resolve_zip(source: str | Path, destination: str | Path) -> RepoSnapshot:
    """Validate and safely extract a repository ZIP into ``destination``."""
    archive_path = Path(source).expanduser()
    if not archive_path.exists():
        raise FileNotFoundError(f"ZIP archive not found: {archive_path}")
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError(f"ZIP source must be a regular file: {archive_path}")

    root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"Invalid ZIP archive: {archive_path}") from exc

    with archive:
        entries = archive.infolist()
        if not entries:
            raise ValueError("ZIP archive is empty.")
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise ValueError(f"ZIP archive exceeds the {MAX_ARCHIVE_ENTRIES} entry limit.")
        total_size = sum(info.file_size for info in entries)
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP archive exceeds the uncompressed size limit.")

        targets: dict[str, bool] = {}
        for info in entries:
            relative, is_dir = _validated_member(info)
            key = relative.as_posix().casefold()
            if key in targets:
                raise ValueError(f"ZIP archive contains duplicate path: {info.filename}")
            targets[key] = is_dir
            if not is_dir and any(existing.startswith(f"{key}/") for existing in targets):
                raise ValueError(f"ZIP entry conflicts with a directory: {info.filename}")
            for parent in relative.parents:
                parent_key = parent.as_posix().casefold()
                if parent_key in targets and not targets[parent_key]:
                    raise ValueError(f"ZIP entry conflicts with a file: {info.filename}")
            if not is_dir and info.file_size:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ValueError("ZIP archive exceeds the compression ratio limit.")

        total_written = 0
        for info in entries:
            relative, is_dir = _validated_member(info)
            target = (root / Path(*relative.parts)).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"ZIP entry escapes extraction directory: {info.filename}")
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            member_written = 0
            try:
                with archive.open(info, "r") as source_stream, target.open("xb") as output:
                    while chunk := source_stream.read(_COPY_CHUNK_SIZE):
                        member_written += len(chunk)
                        total_written += len(chunk)
                        if member_written > info.file_size:
                            raise ValueError(f"ZIP member exceeds declared size: {info.filename}")
                        if total_written > MAX_UNCOMPRESSED_BYTES:
                            raise ValueError("ZIP archive exceeds the uncompressed size limit.")
                        if member_written / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO:
                            raise ValueError("ZIP archive exceeds the compression ratio limit.")
                        output.write(chunk)
                if member_written != info.file_size:
                    raise ValueError(f"ZIP member size does not match metadata: {info.filename}")
            except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
                raise ValueError(f"Corrupted ZIP member: {info.filename}") from exc

    resolved_archive = archive_path.resolve()
    repository_id = hashlib.sha256(str(resolved_archive).encode("utf-8")).hexdigest()[:12]
    repository = RepositoryInfo(
        repository_id=repository_id,
        name=archive_path.stem,
        source_type="zip",
        source_uri=resolved_archive.as_uri(),
    )
    return RepoSnapshot(root_path=root, repository=repository)


def _validated_member(info: zipfile.ZipInfo) -> tuple[PurePosixPath, bool]:
    name = info.filename
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError(f"Unsafe ZIP entry path: {name!r}")
    raw_parts = name.rstrip("/").split("/")
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError(f"Unsafe ZIP entry path: {name!r}")
    if raw_parts[0].endswith(":") or name.startswith("//"):
        raise ValueError(f"Unsafe ZIP entry path: {name!r}")
    relative = PurePosixPath(*raw_parts)
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    is_dir = info.is_dir()
    if file_type == stat.S_IFLNK:
        raise ValueError(f"Symbolic links are not allowed in ZIP archives: {name}")
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise ValueError(f"Special filesystem entry is not allowed: {name}")
    if is_dir and file_type not in {0, stat.S_IFDIR}:
        raise ValueError(f"Invalid directory entry: {name}")
    if not is_dir and file_type == stat.S_IFDIR:
        raise ValueError(f"Invalid file entry: {name}")
    return relative, is_dir
