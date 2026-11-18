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


def _needs_space(path: str, size: int) -> int:
    try:
        if os.path.getsize(path) == size:
            return 0
    except OSError:
        pass
    return size


def export(occurrences: list[Occurrence], target_dir: str, hexdump: bool = False,
           free_space_of: Callable[[str], int] | None = None) -> int:
    """Write every distinct content once and the overview; return the number of errors."""
    if free_space_of is None:
        free_space_of = free_space
    ordered = sorted(occurrences, key=Occurrence.sort_key)
    errors = 0
    by_hash: dict[str, str] = {}
    used: set[str] = set()
    rows = []
    to_write = []  # (occurrence, target, size, hexdump size)
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
        try:
            data = item.read()
            digest = hashlib.sha256(data).hexdigest()
            row['size'] = str(len(data))
            row['data_kind'] = describe_data_kind(data, item.method, item.method_source)
            dump_size = hexdump_size(data) if hexdump else 0
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
            continue
        target = item.target
        number = 1
        while target.lower() in used:
            number += 1
            target = _numbered(item.target, number)
        used.add(target.lower())
        by_hash[digest] = target
        row['written_file'] = target
        row['duplicate'] = 'no'
        to_write.append((item, target, len(data), dump_size))

    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(OVERVIEW_COLUMNS)
    for row in rows:
        writer.writerow([row[column] for column in OVERVIEW_COLUMNS])
    overview = buffer.getvalue()
    overview_bytes = overview.encode('utf-8')

    needed = _needs_space(overview_path(target_dir), len(overview_bytes))
    for _, target, size, dump_size in to_write:
        path = _disk_path(target_dir, target)
        needed += _needs_space(path, size)
        if hexdump:
            needed += _needs_space(path + '.hexdump.txt', dump_size)
    free = free_space_of(target_dir)
    if needed > free:
        raise InsufficientSpaceError(needed, free)

    for item, target, _, _ in to_write:
        path = _disk_path(target_dir, target)
        try:
            data = item.read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as handle:
                handle.write(data)
            if hexdump:
                write_hexdump(data, path + '.hexdump.txt')
        except Exception as error:
            errors += 1
            print('error writing %s block %s: %s' % (item.source, item.block or item.block_index,
                                                      type(error).__name__), file=sys.stderr)
    os.makedirs(os.path.dirname(overview_path(target_dir)), exist_ok=True)
    with open(overview_path(target_dir), 'w', encoding='utf-8', newline='') as handle:
        handle.write(overview)
    return errors
