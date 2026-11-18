"""Flash data of the PIDT workspace: vehicle platforms, PDX packages and loose ODX files."""
import os
import re
import sys
import zipfile
from typing import Callable

from flash_export.odx_flash import (
    OdxFlashDocument, is_flash_document, read_flash_document, read_intern_data)
from flash_export.output import Occurrence, sanitize_name

SOURCE_PDX = 1
SOURCE_LOOSE_ODX = 2
SOURCE_PCC = 3
MAPPING_FILE = 'mapping.properties'
_MAPPING_PREFIX = 'pidt-vehicle-platform.'
_METHOD_SOURCE = 'ENCRYPT-COMPRESS-METHOD'
_ODX_EXTENSIONS = ('.odx', '.odx-f')


def _subfolder(parent: str, name: str) -> str | None:
    """The actual name of the sub folder ``name`` of ``parent``, ignoring case."""
    try:
        for entry in sorted(os.listdir(parent)):
            if entry.lower() == name.lower() and os.path.isdir(os.path.join(parent, entry)):
                return entry
    except OSError:
        pass
    return None


def _flash_folder_parts(workspace_dir: str, platform: str) -> list[str] | None:
    """The folder names of ``<platform>/flash-data/flash-data`` as found on disk, or None."""
    parts = [platform]
    for wanted in ('flash-data', 'flash-data'):
        found = _subfolder(os.path.join(workspace_dir, *parts), wanted)
        if found is None:
            return None
        parts.append(found)
    return parts


def workspace_platforms(workspace_dir: str) -> list[str]:
    """Sub folders of the workspace that contain flash-data/flash-data or mcr-data, sorted."""
    platforms = []
    for name in sorted(os.listdir(workspace_dir)):
        path = os.path.join(workspace_dir, name)
        if not os.path.isdir(path):
            continue
        if _flash_folder_parts(workspace_dir, name) is not None or _subfolder(path, 'mcr-data') is not None:
            platforms.append(name)
    return platforms


def read_platform_mapping(workspace_dir: str) -> list[tuple[str, str]]:
    """(folder, regex) pairs of mapping.properties in file order; FileNotFoundError if the file is missing."""
    mapping = []
    with open(os.path.join(workspace_dir, MAPPING_FILE), encoding='iso-8859-1') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or not line.startswith(_MAPPING_PREFIX):
                continue
            key, separator, regex = line.partition('=')
            if separator:
                mapping.append((key[len(_MAPPING_PREFIX):].strip(), regex.strip()))
    return mapping


def platforms_for_project(mapping: list[tuple[str, str]], project_name: str, platforms: list[str]) -> list[str]:
    """Existing platforms whose expression matches the whole project name, like Java String.matches."""
    matched = set()
    for folder, regex in mapping:
        try:
            if re.fullmatch(regex, project_name):
                matched.add(folder)
        except re.error:
            continue
    return [platform for platform in platforms if platform in matched]


class DocumentCache:
    """Holds the decoded data of the most recently loaded document only."""

    def __init__(self):
        self._key = None
        self._value: dict | None = None
        self._reads = 0

    def get(self, key: tuple, load: Callable[[], dict]) -> dict:
        if self._value is None or key != self._key:
            self._value = None  # release the previous document before decoding the next one
            self._value = load()
            self._key = key
            self._reads += 1
        return self._value

    def reads(self) -> int:
        return self._reads


def _has_extension(name: str, extensions: tuple[str, ...]) -> bool:
    return name.lower().endswith(extensions)


def _stem(name: str) -> str:
    return name.rpartition('.')[0] if '.' in name else name


def _error_row(platform: str, source: str, rank: int, detail: str, error: Exception) -> Occurrence:
    return Occurrence(source_rank=rank, origin_kind='workspace', origin=platform, source=source, block_index=0,
                      target=None, read=None, detail=detail,
                      note='error: %s: %s' % (type(error).__name__, error))


def _read_external(archive_path: str, entry: str) -> Callable[[], bytes]:
    def read(archive_path=archive_path, entry=entry) -> bytes:
        with zipfile.ZipFile(archive_path) as archive:
            return archive.read(entry)
    return read


def _read_embedded(cache: DocumentCache, key: tuple, opener: Callable[[], object], name: str) -> Callable[[], bytes]:
    def read(cache=cache, key=key, opener=opener, name=name) -> bytes:
        def load():
            with opener() as stream:
                return read_intern_data(stream)
        return cache.get(key, load)[name]
    return read


def _block_rows(document: OdxFlashDocument, platform: str, rank: int, source: str, detail_name: str,
                folder: str, entries: set[str] | None, archive_path: str | None,
                cache: DocumentCache, embedded_key: tuple, opener: Callable[[], object]) -> list[Occurrence]:
    rows = []
    for block in document.blocks:
        notes = []
        target = None
        read = None
        if block.data_file:
            if entries is not None and block.data_file in entries:
                target = 'flash/workspace/%s/%s' % (folder, sanitize_name(block.data_file))
                read = _read_external(archive_path, block.data_file)
            else:
                notes.append('file not found in package')
        elif block.has_data and block.flash_data is not None:
            target = 'flash/workspace/%s/%s.bin' % (folder, sanitize_name(block.flash_data))
            read = _read_embedded(cache, embedded_key, opener, block.flash_data)
        else:
            notes.append('no flash data in document')
        if not block.part_numbers:
            notes.append('no part number in document')
        rows.append(Occurrence(
            source_rank=rank, origin_kind='workspace', origin=platform, source=source,
            block_index=block.index, target=target, read=read, detail='%s/%d' % (detail_name, block.index),
            ecu='; '.join(document.ecus), part_number='; '.join(block.part_numbers),
            session='; '.join(block.sessions), block=block.name, block_type=block.block_type,
            start_address=block.start_address, uncompressed_size=block.uncompressed_size,
            method=block.method, method_source=_METHOD_SOURCE, note='; '.join(notes)))
    return rows


def _report(path: str, error: Exception) -> None:
    print('error reading %s: %s' % (path, type(error).__name__), file=sys.stderr)


def pdx_occurrences(workspace_dir: str, platform: str, cache: DocumentCache) -> tuple[list[Occurrence], int]:
    """One row per DATABLOCK of every PDX package of the platform; unreadable packages give an error row."""
    parts = _flash_folder_parts(workspace_dir, platform)
    if parts is None:
        return [], 0
    folder_path = os.path.join(workspace_dir, *parts)
    occurrences: list[Occurrence] = []
    errors = 0
    for name in sorted(os.listdir(folder_path)):
        archive_path = os.path.join(folder_path, name)
        if not _has_extension(name, ('.pdx',)) or not os.path.isfile(archive_path):
            continue
        package_source = '/'.join(parts + [name])
        try:
            rows = []
            with zipfile.ZipFile(archive_path) as archive:
                entries = set(archive.namelist())
                found = False
                for entry in sorted(entries):
                    if not _has_extension(entry, _ODX_EXTENSIONS):
                        continue
                    with archive.open(entry) as stream:
                        if not is_flash_document(stream):
                            continue
                    found = True
                    with archive.open(entry) as stream:
                        document = read_flash_document(stream)
                    rows.extend(_block_rows(
                        document, platform, SOURCE_PDX, package_source + '/' + entry, entry,
                        sanitize_name(_stem(name)), entries, archive_path, cache, (archive_path, entry),
                        lambda archive_path=archive_path, entry=entry: _open_entry(archive_path, entry)))
                if not found:
                    raise ValueError('no ODX flash document in package')
            occurrences.extend(rows)
        except Exception as error:
            errors += 1
            _report(archive_path, error)
            occurrences.append(_error_row(platform, package_source, SOURCE_PDX, name, error))
    return occurrences, errors


class _EntryStream:
    """Context manager that opens one archive entry and closes the archive with it."""

    def __init__(self, archive_path: str, entry: str):
        self._archive = zipfile.ZipFile(archive_path)
        self._stream = self._archive.open(entry)

    def __enter__(self):
        return self._stream

    def __exit__(self, *exc_info):
        self._stream.close()
        self._archive.close()


def _open_entry(archive_path: str, entry: str) -> _EntryStream:
    return _EntryStream(archive_path, entry)


def loose_odx_occurrences(workspace_dir: str, platform: str, cache: DocumentCache) -> tuple[list[Occurrence], int]:
    """One row per DATABLOCK of every loose ODX file of the platform; unreadable files give an error row."""
    parts = _flash_folder_parts(workspace_dir, platform)
    if parts is None:
        return [], 0
    folder_path = os.path.join(workspace_dir, *parts)
    occurrences: list[Occurrence] = []
    errors = 0
    for name in sorted(os.listdir(folder_path)):
        path = os.path.join(folder_path, name)
        if not _has_extension(name, ('.odx',)) or not os.path.isfile(path):
            continue
        source = '/'.join(parts + [name])
        try:
            with open(path, 'rb') as stream:
                if not is_flash_document(stream):
                    raise ValueError('not an ODX flash document')
            with open(path, 'rb') as stream:
                document = read_flash_document(stream)
            occurrences.extend(_block_rows(
                document, platform, SOURCE_LOOSE_ODX, source, name, sanitize_name(_stem(name)), None, None,
                cache, (path,), lambda path=path: open(path, 'rb')))
        except Exception as error:
            errors += 1
            _report(path, error)
            occurrences.append(_error_row(platform, source, SOURCE_LOOSE_ODX, name, error))
    return occurrences, errors
