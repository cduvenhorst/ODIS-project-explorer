"""The remaining files of a project (ODX sources, catalogues, INI), selected by a general rule."""
import os

from flash_export.output import PlainFile
from flash_export.project_sources import CONFIG_FOLDER_PREFIX, FLASH_FOLDER, project_file_index

_EXCLUDED_PREFIXES = ('AStringData', 'UStringData', 'SDG_')
_EXCLUDED_SUFFIXES = ('', '.db', '.key', '.jar', '.class', '.dll', '.exe', '.zip')


def is_other_project_file(relative_path: str) -> bool:
    """True for a file that is neither pool data, flash data, configuration data nor a program."""
    *folders, name = relative_path.split('/')
    if name.startswith(_EXCLUDED_PREFIXES):
        return False
    if os.path.splitext(name)[1].lower() in _EXCLUDED_SUFFIXES:
        return False
    return FLASH_FOLDER not in folders and not any(folder.startswith(CONFIG_FOLDER_PREFIX) for folder in folders)


def other_project_files(project_dir: str, project_name: str) -> list[PlainFile]:
    """The other project files below ``project_dir``, targeted under ``project_name`` and sorted by target."""
    files = [PlainFile(target='%s/%s' % (project_name, path),
                       path=os.path.join(project_dir, *path.split('/')))
             for path in project_file_index(project_dir).values() if is_other_project_file(path)]
    return sorted(files, key=lambda file: file.target)
