import argparse
import os
import time
import traceback

from common_utils import enum_converters, object_printer
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from classes.ObjectLoader import ObjectLoader

from common_utils.layer_chain import load_layer_data
from common_utils.table_entries import KIND_ADAPTATION, TableEntryReader
from dumpMWB import get_protocol_layer_data_list, get_ecu_variant_map, get_ecu_variant_layer_data


# PBL is needed for parsing .key files, which will be done by the PblRecordManager class
# The file "pbl.dll" should be in the working directory, in the "bin" folder
pbl_dll_path = os.path.join(os.path.abspath(os.getcwd()), 'bin/pbl.dll')
pbl_record_manager = PblRecordManager(pbl_dll_path)


def dump_adaptations_for_base_variant(object_loader, project_folder_path, base_variant_filename, output_folder_path, overwrite = False, debug_info_indentation_level = 0):
    # The PoolID simply refers to the file's name (without extension)
    pool_id = base_variant_filename
    if base_variant_filename.endswith('.db'):
        pool_id = base_variant_filename[:-3]
    
    # Only parse a .bv.db file
    if enum_converters.get_db_file_type(pool_id) != 'Base Variant':
        raise RuntimeError('A BASE-VARIANT database must be provided (.bv.db)')
    
    # Only UDS base variants are dumped; the protocol layers follow from the parent layers of the base variant
    protocol_layer_data_list = get_protocol_layer_data_list(object_loader, project_folder_path, pool_id)
    if protocol_layer_data_list is None:
        object_printer.print_indented(debug_info_indentation_level, 'Not UDS')
        return
    
    # Load the Object with ID '#RtGen_DB_PROJECT_DATA', which contains info about the ECU-VARIANTs included in the BASE-VARIANT
    db_project_data = object_loader.load_object_by_id(project_folder_path, pool_id, '#RtGen_DB_PROJECT_DATA')
    
    # At least one ECU-VARIANT should exist
    ecu_variant_map = get_ecu_variant_map(db_project_data)
    if ecu_variant_map is None:
        object_printer.print_indented(debug_info_indentation_level, 'Has no ECU-VARIANTs')
    
    # Get the BASE-VARIANT's name from the "project data" (could get from filename too)
    base_variant_name = db_project_data['base_variant_reference']['object_id']
    
    # The output folder will be named like the BASE-VARIANT
    base_variant_output_folder_path = os.path.join(output_folder_path, base_variant_name)
    
    # Load the layer data for the BASE-VARIANT, which is contained in the current file
    base_variant_layer_data = object_loader.load_object_by_id(project_folder_path, pool_id, '#RtGen_DB_LAYER_DATA')
    
    # Add the BASE-VARIANT at the front of the map to also get its Adaptations
    if ecu_variant_map is not None:
        original_ecu_variant_map = ecu_variant_map
        ecu_variant_map = {base_variant_name: None}
        ecu_variant_map.update(original_ecu_variant_map)
    else:
        ecu_variant_map = {base_variant_name: None}
    
    # One reader per BASE-VARIANT; it buffers the loaded services and responses across its ECU-VARIANTs
    table_entry_reader = TableEntryReader(object_loader, project_folder_path)
    
    # Go through each ECU-VARIANT referenced by the BASE-VARIANT (and the BASE-VARIANT itself)
    for ecu_variant_name in ecu_variant_map:
        if ecu_variant_name == base_variant_name:
            object_printer.print_indented(debug_info_indentation_level, 'BASE-VARIANT {}'.format(ecu_variant_name))
        else:
            object_printer.print_indented(debug_info_indentation_level, 'ECU-VARIANT {}'.format(ecu_variant_name))
        
        # The Adaptations will be dumped into a file named like the ECU-VARIANT
        # The .c extension is only used for highlighting and block folding in a code editor
        ecu_variant_output_file_path = os.path.join(base_variant_output_folder_path, 'ADP_' + ecu_variant_name + '.c')
        
        # Only dump the Adaptations if the file doesn't already exist (or if overwriting is allowed)
        if not overwrite and (os.path.exists(ecu_variant_output_file_path) and os.path.isfile(ecu_variant_output_file_path)):
            object_printer.print_indented(debug_info_indentation_level + 1, 'Already done, skipping')
        else:
            # The layer data will be needed for getting a list of all Adaptations and also for solving some references
            
            # If parsing the BASE-VARIANT, its layer data was retrieved previously
            if ecu_variant_name == base_variant_name:
                ecu_variant_layer_data = base_variant_layer_data
            # Otherwise, retrieve the ECU-VARIANT's layer data
            else:
                ecu_variant_layer_data = get_ecu_variant_layer_data(object_loader, project_folder_path, ecu_variant_map[ecu_variant_name])
    
            # These objects will be used (in this order) for solving references which don't specify a PoolID
            layer_data_objects = [ecu_variant_layer_data, base_variant_layer_data] + protocol_layer_data_list
            
            # Get the services that write adaptations (the VW service, or every single-DID 0x2E service with the
            # adaptation layout)
            services = table_entry_reader.select_services(ecu_variant_layer_data, KIND_ADAPTATION)
            
            # Skip ECU-VARIANTs which do not have such a service (no file will be created)
            if not services:
                object_printer.print_indented(debug_info_indentation_level + 1, 'Has no Adaptations')
                continue
            
            # Read the Adaptations = calibration data before the file is opened, so a failure leaves no partial file
            entries = table_entry_reader.get_entries(layer_data_objects, services)
            
            # Create the BASE-VARIANT's output folder if it doesn't exist
            if not os.path.isdir(base_variant_output_folder_path):
                os.makedirs(base_variant_output_folder_path)
            
            # Open the output file and dump the Adaptations
            with open(ecu_variant_output_file_path, 'w', encoding='utf-8') as ecu_variant_output_file:
                for entry in entries:
                    object_printer.print_object(entry, '0x{:04X}: {} - {}'.format(entry['did'], entry['long_name_id'], entry['long_name']), 0, ecu_variant_output_file, False)
                    object_printer.print_indented(0, '', ecu_variant_output_file)


def dump_adaptations_for_all_base_variants_in_project(object_loader, project_folder_path, output_folder_path, overwrite = False, debug_info_indentation_level = 0):
    # Go through each file (Pool) in the project folder
    for current_filename in os.listdir(project_folder_path):
        # The PoolID simply refers to the file's name (without extension)
        (PoolID, extension) = os.path.splitext(current_filename)
        
        # Only parse .db files
        db_file_path = os.path.join(project_folder_path, current_filename)
        if not os.path.isfile(db_file_path) or extension != '.db':
            continue
        
        # Only parse .bv.db files
        if enum_converters.get_db_file_type(PoolID) != 'Base Variant':
            continue
        
        # Display the current BASE-VARIANT being dumped
        object_printer.print_indented(debug_info_indentation_level, 'Dumping {}'.format(PoolID))
        
        # Dump the Adaptations with the other function
        dump_adaptations_for_base_variant(object_loader, project_folder_path, PoolID, output_folder_path, overwrite, debug_info_indentation_level + 1)


def dump_adaptations_for_all_base_variants_in_all_projects(project_folder_path, output_folder_path, debug_info_indentation_level = 0):
    # Go through each project in the folder
    for project_name in os.listdir(project_folder_path):
        project_path = os.path.join(project_folder_path, project_name)
        
        # Only parse folders
        if not os.path.isdir(project_path):
            continue
        
        # Display the current project being unpacked
        object_printer.print_indented(debug_info_indentation_level, 'Unpacking {}'.format(project_name))
        
        # A valid project must contain string databases
        # If an error occurs while trying to load them, the project is invalid
        try:
            # Create an instance of the StringStorage class, used for loading the strings database
            # The strings database is unique to each project
            string_storage = StringStorage(project_path)
        except FileNotFoundError:
            object_printer.print_indented(debug_info_indentation_level + 1, 'Invalid project')
            if project_name == '_META':
                object_printer.print_indented(debug_info_indentation_level + 1, 'Did you accidentally provide a specific project folder instead of the folder with all projects?')
            continue
        
        # An instance of the ObjectLoader class is used for loading Objects and References from the BASE-VARIANT Pool
        # The first parameter (instance of the PblRecordManager class) is needed here since PBL records will be handled "internally"
        object_loader = ObjectLoader(pbl_record_manager, string_storage)
        
        # Create the project output folder if it doesn't exist
        project_output_folder_path = os.path.join(output_folder_path, project_name)
        if not os.path.isdir(project_output_folder_path):
            os.makedirs(project_output_folder_path)
        
        # Dump the Adaptations for each ECU-VARIANT in each BASE-VARIANT with the other function
        dump_adaptations_for_all_base_variants_in_project(object_loader, project_path, project_output_folder_path, False, debug_info_indentation_level + 1)

        # The layer data cache keeps the ObjectLoader of this project alive, so drop it
        load_layer_data.cache_clear()


def dumpAdaptations_basevariant(project_folder_path, base_variant_filename, output_folder_path):
    if not os.path.isdir(project_folder_path):
        raise RuntimeError('Project must be folder')
    
    # Create the main output folder if it doesn't exist
    if not os.path.isdir(output_folder_path):
        os.makedirs(output_folder_path)
    
    # The project name is the name of the last folder in the path
    project_name = os.path.basename(project_folder_path)
    
    # Create the project's output folder if it doesn't exist
    project_output_folder_path = os.path.join(output_folder_path, project_name)
    if not os.path.isdir(project_output_folder_path):
        os.makedirs(project_output_folder_path)
    
    # Create an instance of the StringStorage class, used for loading the strings database
    # The strings database is unique to each project
    string_storage = StringStorage(project_folder_path)
    
    # An instance of the ObjectLoader class is used for loading Objects and references from the BASE-VARIANT Pool
    object_loader = ObjectLoader(pbl_record_manager, string_storage)
    
    # Some references will only specify the ObjectID (object name) and not the PoolID (file name)
    # To resolve them, there are 3 maps that link an ObjectID with a PoolID: one for the ECU-VARIANT, one for the BASE-VARIANT, and one for the protocol
    # The ObjectID will be searched in them, in that order
    # The maps are contained in the "layer data" object of each database
    
    # Run the app
    dump_adaptations_for_base_variant(object_loader, project_folder_path, base_variant_filename, project_output_folder_path, True)


def dumpAdaptations_project(project_folder_path, output_folder_path):
    if not os.path.isdir(project_folder_path):
        raise RuntimeError('Project must be folder')
    
    # Create the main output folder if it doesn't exist
    if not os.path.isdir(output_folder_path):
        os.makedirs(output_folder_path)
    
    # The project name is the name of the last folder in the path
    project_name = os.path.basename(project_folder_path)
    
    # Create the project's output folder if it doesn't exist
    project_output_folder_path = os.path.join(output_folder_path, project_name)
    if not os.path.isdir(project_output_folder_path):
        os.makedirs(project_output_folder_path)
    
    # Create an instance of the StringStorage class, used for loading the strings database
    # The strings database is unique to each project
    string_storage = StringStorage(project_folder_path)
    
    # An instance of the ObjectLoader class is used for loading Objects and References from the BASE-VARIANT Pool
    object_loader = ObjectLoader(pbl_record_manager, string_storage)
    
    # Get the starting timestamp
    start_time = time.time()
    
    # Run the app
    # Catch any exceptions, so the elapsed time can be displayed even if an unpacking error occurs
    try:
        dump_adaptations_for_all_base_variants_in_project(object_loader, project_folder_path, project_output_folder_path)
    except:
        print('Error:\n{}'.format(traceback.format_exc()))
    
    # Get the elapsed time and split it into hours, minutes, seconds
    elapsed_seconds = time.time() - start_time
    (hours, remainder) = divmod(elapsed_seconds, 3600)
    (minutes, seconds) = divmod(remainder, 60)
    
    # Display the time taken by the script to run
    print('\nElapsed: {:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds)))


def dumpAdaptations_projects(projects_folder_path, output_folder_path):
    if not os.path.isdir(projects_folder_path):
        raise RuntimeError('Must provide folder to all projects')
    
    # Create the main output folder if it doesn't exist
    if not os.path.isdir(output_folder_path):
        os.makedirs(output_folder_path)
    
    # Get the starting timestamp
    start_time = time.time()
    
    # Run the app
    # Catch any exceptions, so the elapsed time can be displayed even if an unpacking error occurs
    try:
        dump_adaptations_for_all_base_variants_in_all_projects(projects_folder_path, output_folder_path)
    except:
        print('Error:\n{}'.format(traceback.format_exc()))
    
    # Get the elapsed time and split it into hours, minutes, seconds
    elapsed_seconds = time.time() - start_time
    (hours, remainder) = divmod(elapsed_seconds, 3600)
    (minutes, seconds) = divmod(remainder, 60)
    
    # Display the time taken by the script to run
    print('\nElapsed: {:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds)))


# Handle usage as script
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dump Adaptation (calibration data) definitions')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # All Adaptations from all ECU-VARIANTs in a BASE-VARIANT of a project
    parser_basevariant = subparsers.add_parser('basevariant', help='Dump Adaptations for all ECU-VARIANTs in a BASE-VARIANT')
    parser_basevariant.add_argument('project_folder_path', help='MCD project (folder containing .db and .key files)')
    parser_basevariant.add_argument('base_variant_filename', help='Filename of BASE-VARIANT (.bv.db file)')
    parser_basevariant.add_argument('output_folder_path', help='Path of folder where to write the dump files, in a separate folder for the project and BASE-VARIANT')
    parser_basevariant.set_defaults(func=dumpAdaptations_basevariant)
    
    # All Adaptations from all ECU-VARIANTs in all BASE-VARIANTs of a project
    parser_project = subparsers.add_parser('project', help='Dump Adaptations for all ECU-VARIANTs in all BASE-VARIANTs of a project')
    parser_project.add_argument('project_folder_path', help='MCD project (folder containing .db and .key files)')
    parser_project.add_argument('output_folder_path', help='Path of folder where to write the dump files, in a separate folder for the project and each BASE-VARIANT')
    parser_project.set_defaults(func=dumpAdaptations_project)
    
    # All Adaptations from all ECU-VARIANTs in all BASE-VARIANTs of all projects
    parser_all_projects = subparsers.add_parser('projects', help='Dump Adaptations for all ECU-VARIANTs in all BASE-VARIANTs of all projects')
    parser_all_projects.add_argument('projects_folder_path', help='MCD projects (folder containing folders containing .db and .key files)')
    parser_all_projects.add_argument('output_folder_path', help='Path of folder where to write the dump files, in a separate folder for each project')
    parser_all_projects.set_defaults(func=dumpAdaptations_projects)
    
    # Parse the provided arguments and call the appropriate function based on the command
    args = parser.parse_args()
    filtered_args = {k: v for k, v in vars(args).items() if k not in ('func', 'command')}
    args.func(**filtered_args)
