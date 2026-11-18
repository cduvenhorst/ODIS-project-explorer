"""Flash data of the PIDT workspace: vehicle platforms, PDX packages and loose ODX files."""
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from typing import Callable

from flash_export.odx_flash import (
    OdxFlashDocument, is_flash_document, read_flash_document, read_intern_data)
from flash_export.output import Occurrence, sanitize_name
from flash_export.sw_cnt import read_sw_cnt_areas

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
    """Existing platforms whose expression matches the whole project name, like Java String.matches.

    An invalid expression raises ValueError.
    """
    matched = set()
    for folder, regex in mapping:
        try:
            if re.fullmatch(regex, project_name):
                matched.add(folder)
        except re.error as error:
            raise ValueError('invalid regular expression for %s in %s: %s' % (folder, MAPPING_FILE, error)) from error
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


def _pcc_paths(workspace_dir: str, platform: str) -> list[tuple[str, list[str]]]:
    """(workspace-relative path parts, absolute path) of every .pcc below mcr-data, sorted by relative path."""
    mcr = _subfolder(os.path.join(workspace_dir, platform), 'mcr-data')
    if mcr is None:
        return []
    base = os.path.join(workspace_dir, platform, mcr)
    found = []
    for folder, _, names in os.walk(base):
        for name in names:
            path = os.path.join(folder, name)
            if _has_extension(name, ('.pcc',)) and os.path.isfile(path):
                relative = os.path.relpath(path, base).split(os.sep)
                found.append(([platform, mcr] + relative, path))
    found.sort(key=lambda item: item[0])
    return [(path, parts) for parts, path in found]


def _read_areas(cache: DocumentCache, key: tuple, archive_path: str, entry: str, index: int) -> Callable[[], bytes]:
    def read(cache=cache, key=key, archive_path=archive_path, entry=entry, index=index) -> bytes:
        def load():
            areas = read_sw_cnt_areas(_read_external(archive_path, entry)())
            return {area.index: area.data for area in areas or [] if area.data is not None}
        data = cache.get(key, load)
        if index not in data:
            raise ValueError('no data for area %d of %s' % (index, entry))
        return data[index]
    return read


def _area_rows(areas: list, platform: str, source: str, entry: str, folder: str,
               cache: DocumentCache, archive_path: str) -> list[Occurrence]:
    rows = []
    for area in areas:
        if area.data is None:
            target, read, note = None, None, 'could not decode container block'
        else:
            name = sanitize_name(area.name) if area.name else 'bereich_%d' % area.index
            target = 'flash/workspace/%s/%s.bin' % (folder, name)
            read = _read_areas(cache, (archive_path, entry), archive_path, entry, area.index)
            note = 'decoded from container (Base64)'
        rows.append(Occurrence(
            source_rank=SOURCE_PCC, origin_kind='pcc', origin=platform, source=source, block_index=area.index,
            target=target, read=read, detail='%s/%d' % (entry, area.index), block=area.name,
            start_address=area.start_address, uncompressed_size=area.uncompressed_size, method=None, note=note))
    return rows


def _entry_rows(archive: zipfile.ZipFile, entry: str, platform: str, source: str, archive_path: str,
                package: str, entries: set[str], cache: DocumentCache) -> list[Occurrence]:
    """Rows of one package entry: data set blocks, container areas or the unchanged entry."""
    folder = '%s/%s' % (sanitize_name(package), sanitize_name(_stem(entry)))
    if _has_extension(entry, _ODX_EXTENSIONS):
        with archive.open(entry) as stream:
            flash = is_flash_document(stream)
        if flash:
            with archive.open(entry) as stream:
                document = read_flash_document(stream)
            rows = _block_rows(
                document, platform, SOURCE_PCC, source, entry, folder, entries, archive_path, cache,
                (archive_path, entry), lambda: _open_entry(archive_path, entry))
            for row in rows:
                row.origin_kind = 'pcc'
            return rows
    elif _has_extension(entry, ('.xml',)):
        try:
            areas = read_sw_cnt_areas(archive.read(entry))
        except ET.ParseError:
            areas = None
        if areas is not None:
            return _area_rows(areas, platform, source, entry, folder, cache, archive_path)
    return [Occurrence(
        source_rank=SOURCE_PCC, origin_kind='pcc', origin=platform, source=source, block_index=0,
        target='mcr/%s/%s' % (sanitize_name(package), sanitize_name(entry)),
        read=_read_external(archive_path, entry), detail=entry, note='package entry, unchanged')]


def pcc_occurrences(workspace_dir: str, platform: str, cache: DocumentCache) -> tuple[list[Occurrence], int]:
    """Rows of every PCC package of the platform; unreadable packages and entries give an error row."""
    occurrences: list[Occurrence] = []
    errors = 0
    for archive_path, parts in _pcc_paths(workspace_dir, platform):
        package_source = '/'.join(parts)
        package = _stem(parts[-1])
        try:
            archive = zipfile.ZipFile(archive_path)
        except Exception as error:
            errors += 1
            _report(archive_path, error)
            occurrences.append(_pcc_error(platform, package_source, parts[-1], error))
            continue
        with archive:
            entries = {name for name in archive.namelist() if not name.endswith('/')}
            for entry in sorted(entries):
                source = package_source + '/' + entry
                try:
                    occurrences.extend(_entry_rows(
                        archive, entry, platform, source, archive_path, package, entries, cache))
                except Exception as error:
                    errors += 1
                    _report(archive_path + '/' + entry, error)
                    occurrences.append(_pcc_error(platform, source, entry, error))
    return occurrences, errors


def _pcc_error(platform: str, source: str, detail: str, error: Exception) -> Occurrence:
    row = _error_row(platform, source, SOURCE_PCC, detail, error)
    row.origin_kind = 'pcc'
    return row


def workspace_occurrences(workspace_dir: str, platforms: list[str],
                          progress: Callable[[str], None] | None = None) -> tuple[list[Occurrence], int]:
    """PDX, loose ODX and PCC rows of the given platforms, in that order per platform, and the error count."""
    cache = DocumentCache()
    occurrences: list[Occurrence] = []
    errors = 0
    for platform in platforms:
        if progress is not None:
            progress(platform)
        for collect in (pdx_occurrences, loose_odx_occurrences, pcc_occurrences):
            rows, count = collect(workspace_dir, platform, cache)
            occurrences.extend(rows)
            errors += count
    return occurrences, errors
