import argparse
import os
import sys
import time

from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from classes.ObjectLoader import ObjectLoader

from flash_export.output import InsufficientSpaceError, OutputFolderError, export, overview_path
from flash_export.project_sources import project_occurrences


def create_pbl_record_manager():
    # PBL is needed for parsing .key files, which will be done by the PblRecordManager class
    # The file "pbl.dll" should be in the working directory, in the "bin" folder
    pbl_dll_path = os.path.join(os.path.abspath(os.getcwd()), 'bin/pbl.dll')
    return PblRecordManager(pbl_dll_path)


def is_inside(path, folder):
    real_path = os.path.realpath(path)
    real_folder = os.path.realpath(folder)
    if real_path == real_folder or real_path.startswith(real_folder.rstrip(os.sep) + os.sep):
        return True
    # On case-insensitive file systems the spelling may differ, so compare every existing ancestor by identity
    current = os.path.abspath(path)
    while True:
        if os.path.exists(current) and os.path.samefile(current, folder):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def print_elapsed(start_time):
    # Get the elapsed time and split it into hours, minutes, seconds
    elapsed_seconds = time.time() - start_time
    (hours, remainder) = divmod(elapsed_seconds, 3600)
    (minutes, seconds) = divmod(remainder, 60)
    print('\nElapsed: {:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds)))


def finish(occurrences, errors, output_folder_path, hexdump, start_time):
    try:
        errors += export(occurrences, output_folder_path, hexdump)
    except InsufficientSpaceError as error:
        print('Not enough free space in {}: needed {} bytes, free {} bytes'.format(output_folder_path, error.needed, error.free))
        print_elapsed(start_time)
        return 1
    except OutputFolderError as error:
        print('Cannot create output folder {}: {}'.format(error.path, type(error.cause).__name__))
        print_elapsed(start_time)
        return 1
    if errors > 0:
        print('Errors: {}'.format(errors))
    print('Overview: {}'.format(overview_path(output_folder_path)))
    print_elapsed(start_time)
    return 1 if errors > 0 else 0


def dumpFlash_project(project_folder_path, output_folder_path, hexdump=False, pbl_record_manager=None):
    if not os.path.isdir(project_folder_path):
        print('Project must be folder')
        return 1
    
    # The output must not be written into the data being read
    if is_inside(output_folder_path, project_folder_path):
        print('Output folder must not be inside the source folder')
        return 1
    
    start_time = time.time()
    if pbl_record_manager is None:
        pbl_record_manager = create_pbl_record_manager()
    
    # The project name is the name of the project folder itself, also for '.' or '..' as path
    project_name = os.path.basename(os.path.abspath(project_folder_path))
    print('Collecting {}'.format(project_name))
    
    try:
        string_storage = StringStorage(project_folder_path)
    except FileNotFoundError:
        print('    Invalid project')
        return 1
    object_loader = ObjectLoader(pbl_record_manager, string_storage)
    occurrences, errors = project_occurrences(object_loader, project_folder_path, project_name)
    return finish(occurrences, errors, output_folder_path, hexdump, start_time)


def dumpFlash_projects(projects_folder_path, output_folder_path, hexdump=False, pbl_record_manager=None):
    if not os.path.isdir(projects_folder_path):
        print('Must provide folder to all projects')
        return 1
    
    # The output must not be written into the data being read
    if is_inside(output_folder_path, projects_folder_path):
        print('Output folder must not be inside the source folder')
        return 1
    
    start_time = time.time()
    if pbl_record_manager is None:
        pbl_record_manager = create_pbl_record_manager()
    
    # All occurrences of all projects go into one export, so identical content is written once per run
    occurrences = []
    errors = 0
    for project_name in sorted(os.listdir(projects_folder_path)):
        project_path = os.path.join(projects_folder_path, project_name)
        
        # Only parse folders
        if not os.path.isdir(project_path):
            continue
        
        print('Collecting {}'.format(project_name))
        
        # A valid project must contain string databases
        try:
            string_storage = StringStorage(project_path)
        except FileNotFoundError:
            print('    Invalid project')
            if project_name == '_META':
                print('    Did you accidentally provide a specific project folder instead of the folder with all projects?')
            continue
        
        object_loader = ObjectLoader(pbl_record_manager, string_storage)
        project_items, project_errors = project_occurrences(object_loader, project_path, project_name)
        occurrences.extend(project_items)
        errors += project_errors
    return finish(occurrences, errors, output_folder_path, hexdump, start_time)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Dump flash data, seed key programs and decoded flash containers as binary files')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # All flash data of one project
    parser_project = subparsers.add_parser('project', help='Dump the flash data of a project')
    parser_project.add_argument('project_folder_path', help='MCD project (folder containing .db and .key files)')
    parser_project.add_argument('output_folder_path', help='Path of folder where to write the dump files, below "flash" and in a separate folder for the project')
    parser_project.add_argument('--hexdump', action='store_true', help='Also write a text hexdump next to each dumped file')
    parser_project.set_defaults(func=dumpFlash_project)
    
    # All flash data of all projects
    parser_all_projects = subparsers.add_parser('projects', help='Dump the flash data of all projects')
    parser_all_projects.add_argument('projects_folder_path', help='MCD projects (folder containing folders containing .db and .key files)')
    parser_all_projects.add_argument('output_folder_path', help='Path of folder where to write the dump files, below "flash" and in a separate folder for each project')
    parser_all_projects.add_argument('--hexdump', action='store_true', help='Also write a text hexdump next to each dumped file')
    parser_all_projects.set_defaults(func=dumpFlash_projects)
    
    # Parse the provided arguments and call the appropriate function based on the command
    args = parser.parse_args(argv)
    filtered_args = {k: v for k, v in vars(args).items() if k not in ('func', 'command')}
    return args.func(**filtered_args)


# Handle usage as script
if __name__ == '__main__':
    sys.exit(main())
