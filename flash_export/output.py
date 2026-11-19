"""Shared output stage of the flash export: deduplication, space check, writing, overview."""
import csv
import hashlib
import io
import os
import re
import shutil
import sys
from dataclasses import dataclass
from typing import Callable

from flash_export.data_kind import describe_data_kind
from flash_export.hexdump import hexdump_size, write_hexdump

SOURCE_PROJECTS = 0
OVERVIEW_COLUMNS = ['origin_kind', 'origin', 'source', 'ecu', 'part_number', 'session', 'block', 'block_type',
                    'start_address', 'size', 'uncompressed_size', 'method', 'data_kind', 'written_file',
                    'duplicate', 'note']

_UNSAFE = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


@dataclass(frozen=True)
class PlainFile:
    """A file copied unchanged: ``target`` is the relative '/'-path below the output, ``path`` the source file."""
    target: str
    path: str


@dataclass
class Occurrence:
    source_rank: int
    origin_kind: str
    origin: str
    source: str
    block_index: int
    target: str | None
    read: Callable[[], bytes] | None
    detail: str = ''
    ecu: str = ''
    part_number: str = ''
    session: str = ''
    block: str = ''
    block_type: str = ''
    start_address: int | None = None
    uncompressed_size: int | None = None
    method: int | None = None
    method_source: str = ''
    note: str = ''

    def sort_key(self) -> tuple:
        return self.source_rank, self.origin, self.source, self.block_index, self.detail


class InsufficientSpaceError(Exception):
    def __init__(self, needed: int, free: int):
        super().__init__('not enough free space: %d bytes needed, %d bytes free' % (needed, free))
        self.needed = needed
        self.free = free


class OutputFolderError(OSError):
    def __init__(self, path: str, cause: OSError):
        super().__init__('cannot create output folder %s: %s' % (path, type(cause).__name__))
        self.path = path
        self.cause = cause


def sanitize_name(name: str) -> str:
    """Replace characters that are not allowed in file names by '_'."""
    name = _UNSAFE.sub('_', name)
    return '_' if name in ('', '.', '..') else name


def free_space(path: str) -> int:
    """Free bytes of the nearest existing folder at or above ``path``."""
    path = os.path.abspath(path)
    while not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return shutil.disk_usage(path).free


def overview_path(target_dir: str) -> str:
    return os.path.join(target_dir, 'flash', 'flash_overview.csv')


def _numbered(target: str, number: int) -> str:
    folder, _, name = target.rpartition('/')
    stem, dot, extension = name.rpartition('.')
    if not dot or not stem:
        stem, extension = name, ''
    else:
        extension = '.' + extension
    return (folder + '/' if folder else '') + '%s_%d%s' % (stem, number, extension)


def _hex(value: int | None, width: int) -> str:
    return '' if value is None else '0x%0*X' % (width, value)


def _disk_path(target_dir: str, relative: str) -> str:
    return os.path.join(target_dir, *relative.split('/'))


def _is_safe_target(target: str) -> bool:
    """A target is a relative '/'-path without empty, '.' or '..' parts and without backslashes."""
    return not target.startswith('/') and '\\' not in target and not any(
        part in ('', '.', '..') for part in target.split('/'))


def _needs_space(path: str, size: int) -> int:
    try:
        if os.path.getsize(path) == size:
            return 0
    except OSError:
        pass
    return size


def _overview_text(rows: list[dict]) -> str:
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(OVERVIEW_COLUMNS)
    for row in rows:
        writer.writerow([row[column] for column in OVERVIEW_COLUMNS])
    return buffer.getvalue()


def export(occurrences: list[Occurrence], target_dir: str, hexdump: bool = False,
           free_space_of: Callable[[str], int] | None = None, plain_files: list[PlainFile] | None = None) -> int:
    """Write every distinct content once and the overview; return the number of errors.

    ``plain_files`` are copied unchanged: no deduplication, no overview row, no hexdump.
    """
    if free_space_of is None:
        free_space_of = free_space
    ordered = sorted(occurrences, key=Occurrence.sort_key)
    errors = 0
    by_hash: dict[str, str] = {}
    used: set[str] = set()
    duplicates: dict[str, list] = {}
    rows = []
    to_write = []  # (occurrence, row, target, first-pass hash, size, hexdump size)
    for item in ordered:
        row = {'origin_kind': item.origin_kind, 'origin': item.origin, 'source': item.source, 'ecu': item.ecu,
               'part_number': item.part_number, 'session': item.session, 'block': item.block,
               'block_type': item.block_type, 'start_address': _hex(item.start_address, 8), 'size': '',
               'uncompressed_size': '' if item.uncompressed_size is None else str(item.uncompressed_size),
               'method': _hex(item.method, 2), 'data_kind': '', 'written_file': '', 'duplicate': '',
               'note': item.note}
        rows.append(row)
        if item.target is None or item.read is None:
            continue
        if not _is_safe_target(item.target):
            errors += 1
            message = 'error: ValueError: unsafe target path'
            row['note'] = row['note'] + '; ' + message if row['note'] else message
            print('error writing %s block %s: ValueError' % (item.source, item.block or item.block_index),
                  file=sys.stderr)
            continue
        try:
            data = item.read()
            digest = hashlib.sha256(data).hexdigest()
            row['size'] = str(len(data))
            row['data_kind'] = describe_data_kind(data, item.method, item.method_source)
        except Exception as error:
            errors += 1
            message = 'error: %s: %s' % (type(error).__name__, error)
            row['note'] = row['note'] + '; ' + message if row['note'] else message
            print('error reading %s block %s: %s' % (item.source, item.block or item.block_index,
                                                      type(error).__name__), file=sys.stderr)
            continue
        if digest in by_hash:
            row['written_file'] = by_hash[digest]
            row['duplicate'] = 'yes'
            duplicates.setdefault(digest, []).append(row)
            continue
        dump_size = hexdump_size(data) if hexdump else 0
        target = item.target
        number = 1
        while target.lower() in used:
            number += 1
            target = _numbered(item.target, number)
        used.add(target.lower())
        by_hash[digest] = target
        row['written_file'] = target
        row['duplicate'] = 'no'
        to_write.append((item, row, target, digest, len(data), dump_size))

    # Plain files: check target and size before the space check, copy after the flash contents
    to_copy = []  # (target, source path, size)
    reserved = 'flash/flash_overview.csv'
    for plain in plain_files or []:
        try:
            if not _is_safe_target(plain.target):
                raise ValueError('unsafe target path')
            if plain.target.lower() in used or plain.target.lower() == reserved:
                raise ValueError('target already in use')
            size = os.path.getsize(plain.path)
        except Exception as error:
            errors += 1
            print('error copying %s: %s' % (plain.target, type(error).__name__), file=sys.stderr)
            continue
        used.add(plain.target.lower())
        to_copy.append((plain.target, plain.path, size))

    overview = _overview_text(rows)
    overview_bytes = overview.encode('utf-8')

    needed = _needs_space(overview_path(target_dir), len(overview_bytes))
    for _, _, target, _, size, dump_size in to_write:
        path = _disk_path(target_dir, target)
        needed += _needs_space(path, size)
        if hexdump:
            needed += _needs_space(path + '.hexdump.txt', dump_size)
    for target, _, size in to_copy:
        needed += _needs_space(_disk_path(target_dir, target), size)
    free = free_space_of(target_dir)
    if needed > free:
        raise InsufficientSpaceError(needed, free)
    flash_folder = os.path.dirname(overview_path(target_dir))
    try:
        os.makedirs(flash_folder, exist_ok=True)
    except OSError as error:
        raise OutputFolderError(flash_folder, error) from error

    for item, row, target, digest, _, _ in to_write:
        path = _disk_path(target_dir, target)
        try:
            data = item.read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('content changed between reads')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as handle:
                handle.write(data)
            if hexdump:
                write_hexdump(data, path + '.hexdump.txt')
        except Exception as error:
            errors += 1
            for leftover in (path, path + '.hexdump.txt'):
                try:
                    os.remove(leftover)
                except OSError:
                    pass
            message = 'error: %s: %s' % (type(error).__name__, error)
            for failed in [row] + duplicates.get(digest, []):
                failed['note'] = failed['note'] + '; ' + message if failed['note'] else message
                failed['written_file'] = ''
            print('error writing %s block %s: %s' % (item.source, item.block or item.block_index,
                                                      type(error).__name__), file=sys.stderr)
    for target, source, _ in to_copy:
        path = _disk_path(target_dir, target)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copyfile(source, path)
        except Exception as error:
            errors += 1
            try:
                os.remove(path)
            except OSError:
                pass
            print('error copying %s: %s' % (target, type(error).__name__), file=sys.stderr)
    overview = _overview_text(rows)
    with open(overview_path(target_dir), 'w', encoding='utf-8', newline='') as handle:
        handle.write(overview)
    return errors
