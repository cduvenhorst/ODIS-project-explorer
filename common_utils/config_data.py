"""Lists and copies the files of the ConfigData_* folders of a project."""
import fnmatch
import os
import shutil

CONFIG_DATA_PREFIX = 'ConfigData_'


# Names of the ConfigData_* folders of a project
### project_folder_path = Project path
def config_data_folders(project_folder_path: str) -> list[str]:
    return sorted(name for name in os.listdir(project_folder_path)
                  if name.startswith(CONFIG_DATA_PREFIX) and os.path.isdir(os.path.join(project_folder_path, name)))


# Files of a ConfigData folder, also those in subfolders
### folder_name = name of the folder in the project folder, a missing folder has no files
### returns dictionaries with the relative path (with '/') and the size in bytes, sorted by name
def list_config_data_files(project_folder_path: str, folder_name: str) -> list[dict]:
    folder_path = os.path.join(project_folder_path, folder_name)
    files = []
    for directory, _, names in os.walk(folder_path):
        for name in names:
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, folder_path).replace(os.sep, '/')
            files.append({'name': relative, 'size': os.path.getsize(path)})
    return sorted(files, key=lambda file: file['name'])


# Files whose name matches the wildcard pattern (case sensitive)
def matching_config_data_files(files: list[dict], pattern: str) -> list[dict]:
    # kernel: MCDDbDataRecordImpl::getMatchingFileNames uses the coding data file name as a wildcard pattern
    return [file for file in files if fnmatch.fnmatchcase(file['name'], pattern)]


# Copy the files of all ConfigData folders to the output folder, under the same relative path
### overwrite = whether or not to replace a file which already exists in the output folder
def copy_config_data(project_folder_path: str, output_folder_path: str, overwrite: bool) -> None:
    for folder_name in config_data_folders(project_folder_path):
        for file in list_config_data_files(project_folder_path, folder_name):
            relative = folder_name + '/' + file['name']
            target = os.path.join(output_folder_path, *relative.split('/'))
            if os.path.exists(target) and not overwrite:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(os.path.join(project_folder_path, *relative.split('/')), target)
