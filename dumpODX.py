import argparse
import os
from collections import Counter

from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from odx_export.document import build_document, write_document
from odx_export.naming import layer_name
from odx_export.pool_source import ProjectPools


# PBL is needed for parsing .key files, which will be done by the PblRecordManager class
# The file "pbl.dll" should be in the working directory, in the "bin" folder
pbl_dll_path = os.path.join(os.path.abspath(os.getcwd()), 'bin/pbl.dll')
pbl_record_manager = PblRecordManager(pbl_dll_path)


# Messages for a written Pool
### ctx = PoolContext of the Pool after its document was built
### returns the counter line, and the lines for unused objects and objects without a place in ODX if there are any
def report_lines(ctx) -> list[str]:
    report = ctx.report
    lines = ['{}: unresolvable references {}, empty references {}, replaced characters {}, '
             'DISPLAY-RADIX DEC not present {}'.format(ctx.pool_id, report['unresolvable_references'],
                                                       report['empty_references'], report['replaced_characters'],
                                                       report['omitted_display_radix'])]
    unused = ctx.unused()
    if unused:
        lines.append('{}: unused objects {}'.format(ctx.pool_id, _type_counts(unused)))
    without_place = Counter(ctx.types[key] for key in ctx.without_place)
    if without_place:
        lines.append('{}: objects without a place in ODX {}'.format(ctx.pool_id, _type_counts(without_place)))
    return lines


def _type_counts(counter):
    return ', '.join('{} {}'.format(type_name, count) for (type_name, count) in sorted(counter.items()))


# Reconstruct an ODX document for each shared data Pool of an MCD Project
### string_storage      = instance of StringStorage, loaded from the target Project
### project_folder_path = Project path (folder with .db and .key files)
### output_folder_path  = path of folder in which the "odx" folder with the documents is written
def app_dumpODX(string_storage, project_folder_path, output_folder_path):
    pools = ProjectPools(project_folder_path, string_storage, pbl_record_manager)
    odx_folder_path = os.path.join(output_folder_path, 'odx')
    os.makedirs(odx_folder_path, exist_ok=True)

    # One Pool at a time: its objects are released before the next Pool is loaded
    for PoolID in pools.shared_data_pools():
        output_path = os.path.join(odx_folder_path, layer_name(PoolID) + '.odx')
        try:
            ctx = pools.context(PoolID)
            write_document(build_document(ctx), output_path, PoolID)
        except Exception as error:
            # A Pool that cannot be loaded or written is skipped, the other Pools are still written
            # (write_document removes a half-written file)
            print('{}: skipped, cannot be loaded: {!r}'.format(PoolID, error))
            ctx = None
            continue
        for line in report_lines(ctx):
            print(line)
        ctx = None


# Handle usage as script
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reconstruct an ODX document from each shared data Pool of an MCD Project')
    parser.add_argument('project_folder_path', help='MCD Project (folder containing .db and .key files)')
    parser.add_argument('output_folder_path', help='Main output folder, in which another folder with the name of the Project will be added')
    args = parser.parse_args()

    # The project_folder_path argument must be a path to a folder
    if not os.path.isdir(args.project_folder_path):
        raise RuntimeError('Project must be folder')

    # The Project's name is the name of the "last" folder in the path
    project_name = os.path.basename(os.path.normpath(args.project_folder_path))

    # Create the Project's output folder (and the main output folder) if it doesn't exist
    project_output_folder_path = os.path.join(args.output_folder_path, project_name)
    os.makedirs(project_output_folder_path, exist_ok=True)

    # Create an instance of the StringStorage class, used for loading the strings database
    # The strings database is unique to each Project
    string_storage = StringStorage(args.project_folder_path)

    # Run the app
    app_dumpODX(string_storage, args.project_folder_path, project_output_folder_path)
