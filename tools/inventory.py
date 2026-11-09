"""Count, per object type, how many objects of MCD projects decode in strict mode.

Usage: python3 tools/inventory.py --output DIR PROJECT [PROJECT ...]

The output describes proprietary data. It must never be committed, so the
tool refuses to write inside the git working tree it belongs to.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from classes.ObjectLoader import ObjectLoader  # noqa: E402
from classes.PBL import default_library_path  # noqa: E402
from classes.PblRecordManager import PblRecordManager  # noqa: E402
from classes.StringStorage import StringStorage  # noqa: E402
from common_utils import enum_converters  # noqa: E402
from common_utils.diagnostics import UnreadBytesError  # noqa: E402
from object_loaders import __all__ as loadable_types  # noqa: E402

MAX_MESSAGE_LENGTH = 90


def error_text(error):
    """`<ExceptionClassName>: <first message line, at most 90 characters>`."""
    if isinstance(error, UnreadBytesError):
        return 'UnreadBytesError: {} bytes'.format(error.remaining)
    lines = str(error).splitlines()
    first_line = lines[0] if lines else ''
    return '{}: {}'.format(type(error).__name__, first_line[:MAX_MESSAGE_LENGTH])


def type_name_of(code):
    try:
        return enum_converters.get_object_type_enum(code)
    except KeyError:
        return 'UNMAPPED_0x{:04X}'.format(code)


def pool_names(project_folder):
    """Every pool that has a .key or a .db file; a pool with only one of them is broken."""
    stems = set()
    for name in os.listdir(project_folder):
        stem, extension = os.path.splitext(name)
        if extension in ('.key', '.db'):
            stems.add(stem)
    return sorted(stems)


def inventory_project(project_folder, library_path):
    """Read every pool strictly and return the JSON-serialisable result.

    pool_error of a pool is None when the pool was read completely, otherwise
    the text `<ExceptionClassName>: <message>` of the error that stopped it.
    """
    started = time.time()
    records = PblRecordManager(library_path)
    loader = ObjectLoader(None, StringStorage(project_folder), strict=True)
    types = {}
    errors = {}
    pools = {}
    for pool in pool_names(project_folder):
        counts = {'ok': 0, 'failed': 0, 'unknown': 0, 'pool_error': None}
        pools[pool] = counts
        try:
            pool_records = records.get_all_records(project_folder, pool)
            with open(os.path.join(project_folder, pool + '.db'), 'rb') as db_file:
                for record in pool_records.values():
                    data = ObjectLoader.get_object_data_from_opened_db_file(record, db_file)
                    code = struct.unpack('<H', data[:2])[0]
                    name = type_name_of(code)
                    entry = types.setdefault(name, {'code': code, 'ok': 0, 'failed': 0, 'unknown': 0})
                    if name not in loadable_types:
                        entry['unknown'] += 1
                        counts['unknown'] += 1
                        continue
                    try:
                        loader.load_object_by_object_data(data)
                    except Exception as error:  # noqa: BLE001 - every decoding failure is classified
                        key = '{} | {}'.format(name, error_text(error))
                        errors[key] = errors.get(key, 0) + 1
                        entry['failed'] += 1
                        counts['failed'] += 1
                    else:
                        entry['ok'] += 1
                        counts['ok'] += 1
        except Exception as error:  # noqa: BLE001 - a broken pool must not stop the run
            counts['pool_error'] = error_text(error)
    return {'project': project_folder, 'seconds': round(time.time() - started, 2),
            'types': types, 'errors': errors, 'pools': pools}


def output_name(project_folder):
    """`<installation>-<project>`; installation is the folder above Projects-V, else the parent folder."""
    path = os.path.abspath(project_folder)
    project = os.path.basename(path)
    parent = os.path.dirname(path)
    if os.path.basename(parent) == 'Projects-V':
        parent = os.path.dirname(parent)
    return '{}-{}'.format(os.path.basename(parent), project)


def git_output(*arguments):
    result = subprocess.run(['git', *arguments], cwd=REPOSITORY_ROOT,
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def protected_roots():
    """Folders that must never receive output; the first is always the folder above tools/.

    With git these are also the working tree top level and the clone root (the folder
    holding the common .git directory), which covers every worktree of the clone.
    Without git a warning is printed and only the folder above tools/ is protected.
    """
    roots = [os.path.realpath(REPOSITORY_ROOT)]
    try:
        roots.append(os.path.realpath(git_output('rev-parse', '--show-toplevel')))
        common = os.path.realpath(git_output('rev-parse', '--git-common-dir'))
        roots.append(os.path.dirname(common))
    except (OSError, subprocess.CalledProcessError):
        print('Warning: git is not available; only {} is protected against output.'
              .format(roots[0]), file=sys.stderr)
    return roots


def is_inside(path, folder):
    """True if path is folder or below it.

    Existing ancestors of path are compared with os.path.samefile, so symlinks, `..`
    and a different spelling of the case on case-insensitive file systems cannot
    bypass the check. A path that does not exist yet is judged by its ancestors.
    """
    current = os.path.realpath(path)
    while True:
        if os.path.exists(current) and os.path.exists(folder) and os.path.samefile(current, folder):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def summary_lines(name, result):
    pools = result['pools'].values()
    ok = sum(entry['ok'] for entry in result['types'].values())
    failed = sum(entry['failed'] for entry in result['types'].values())
    unknown = sum(entry['unknown'] for entry in result['types'].values())
    broken = sum(1 for entry in pools if entry['pool_error'])
    return '{}: ok={} failed={} unknown={} pool_errors={} (pools: {}, {} s)'.format(
        name, ok, failed, unknown, broken, len(result['pools']), result['seconds'])


def main(arguments=None):
    parser = argparse.ArgumentParser(description='Count strictly decoded objects per type.')
    parser.add_argument('--output', required=True, help='folder for the JSON files; must be outside the repository')
    parser.add_argument('--library', default=default_library_path(REPOSITORY_ROOT), help='PBL library path')
    parser.add_argument('projects', nargs='+', metavar='PROJECT')
    options = parser.parse_args(arguments)

    # All checks come before the first directory or file is created
    for root in protected_roots():
        if is_inside(options.output, root):
            print('Refusing to write inside {}: inventory output must never be committed.'.format(root),
                  file=sys.stderr)
            return 2
    names = [output_name(project) for project in options.projects]
    for project in options.projects:
        if not os.path.isdir(project):
            print('Not a folder: {}'.format(project), file=sys.stderr)
            return 2
    if len(set(names)) != len(names):
        print('Two projects would write the same output file.', file=sys.stderr)
        return 2

    os.makedirs(options.output, exist_ok=True)
    lines = []
    for project, name in zip(options.projects, names):
        result = inventory_project(project, options.library)
        with open(os.path.join(options.output, name + '.json'), 'w', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
        lines.append(summary_lines(name, result))
        print(lines[-1])
    with open(os.path.join(options.output, 'summary.txt'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
