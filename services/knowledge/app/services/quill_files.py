"""Retain imported originals independently of parser temporary directories."""
from pathlib import Path
from shutil import copyfile
from uuid import uuid4


def retain_original(record, source: Path, filename: str | None = None) -> None:
    directory = Path("storage/quill-originals")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / (uuid4().hex + source.suffix.lower())
    copyfile(source, destination)
    record.file_path = str(destination)
    record.file_size = destination.stat().st_size
    if filename:
        record.file_name = Path(filename.replace('\\', '/')).name
