import os
import subprocess
import sys
import tempfile
import unittest

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_VARIANT = '0.0.0@B.bv'

# Message each subcommand prints when its project folder does not exist
MISSING_PROJECT = 'Project must be folder'
MISSING_PROJECTS = 'Must provide folder to all projects'

# Scripts with subcommands and the subcommands each one offers
SUBCOMMAND_SCRIPTS = {
    'dumpAdaptations.py': ('basevariant', 'project', 'projects'),
    'dumpCoding.py': ('basevariant', 'project', 'projects'),
    'dumpDTC.py': ('basevariant', 'project', 'projects'),
    'dumpECUVariantPatterns.py': ('basevariant', 'project', 'projects'),
    'dumpFlash.py': ('project', 'projects'),
    'dumpFreezeFrames.py': ('basevariant', 'project', 'projects'),
    'dumpMWB.py': ('basevariant', 'project', 'projects'),
}

TRANSLATION_SCRIPTS = ('dumpDTC.py',)

# Scripts without subcommands: the required options as (name, value) pairs, the option whose absence
# is tested and the message printed when the project folder does not exist
SINGLE_COMMAND_SCRIPTS = {
    'dumpAllProjects.py': {
        'options': lambda root: [('--projects', os.path.join(root, 'PP')), ('--output', os.path.join(root, 'out'))],
        'omitted': '--output',
        'missing_folder': MISSING_PROJECTS,
    },
    'dumpODX.py': {
        'options': lambda root: [('--project', os.path.join(root, 'P')), ('--output', os.path.join(root, 'out'))],
        'omitted': '--output',
        'missing_folder': MISSING_PROJECT,
    },
    'dumpProject.py': {
        'options': lambda root: [('--project', os.path.join(root, 'P')), ('--output', os.path.join(root, 'out'))],
        'omitted': '--output',
        'missing_folder': MISSING_PROJECT,
    },
    'parseMWB.py': {
        'options': lambda root: [('--project', os.path.join(root, 'P')), ('--base-variant', BASE_VARIANT),
                                 ('--ecu-variant', 'EV_Example'), ('--did', 'F40C'), ('--response', 'C0E4')],
        'omitted': '--did',
        'missing_folder': MISSING_PROJECT,
    },
}

# dumpHSQLDB.py starts a JVM, so it is run with stand-ins for the Java modules
HSQLDB_OPTIONS = [('--database-folder', 'DB'), ('--database-name', 'name'), ('--output', 'out')]


def run_script(*arguments):
    return subprocess.run([sys.executable, '-B', *arguments],
                          cwd=REPOSITORY_ROOT, capture_output=True, text=True)


def required_options(command, root):
    """Required options of a subcommand as (name, value) pairs"""
    output = os.path.join(root, 'out')
    if command == 'basevariant':
        return [('--project', os.path.join(root, 'P')), ('--base-variant', BASE_VARIANT), ('--output', output)]
    if command == 'project':
        return [('--project', os.path.join(root, 'P')), ('--output', output)]
    return [('--projects', os.path.join(root, 'PP')), ('--output', output)]


def flatten(options):
    return [part for pair in options for part in pair]


def run_dump_hsqldb(*arguments):
    code = ("import sys; from unittest import mock; "
            "sys.modules.update({name: mock.MagicMock() for name in ('jpype', 'jpype.imports', 'java', 'java.sql')}); "
            "sys.argv = " + repr(['dumpHSQLDB.py', *arguments]) + "; "
            "exec(compile(open('dumpHSQLDB.py').read(), 'dumpHSQLDB.py', 'exec'))")
    return subprocess.run([sys.executable, '-B', '-c', code],
                          cwd=REPOSITORY_ROOT, capture_output=True, text=True)


def all_subcommands():
    for script, commands in SUBCOMMAND_SCRIPTS.items():
        for command in commands:
            yield script, command


class CommandLineTests(unittest.TestCase):
    def test_positional_form_is_rejected(self):
        for script, command in all_subcommands():
            with self.subTest(script=script, command=command), tempfile.TemporaryDirectory() as root:
                options = required_options(command, root)
                result = run_script(script, command, *[value for _, value in options])
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn('the following arguments are required: ' + options[0][0], result.stderr)
                self.assertFalse(os.path.exists(os.path.join(root, 'out')))

    def test_missing_required_option_is_named(self):
        for script, command in all_subcommands():
            with self.subTest(script=script, command=command), tempfile.TemporaryDirectory() as root:
                options = [pair for pair in required_options(command, root) if pair[0] != '--output']
                result = run_script(script, command, *flatten(options))
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn('the following arguments are required: --output', result.stderr)

    def test_named_form_reaches_the_dump(self):
        for script, command in all_subcommands():
            with self.subTest(script=script, command=command), tempfile.TemporaryDirectory() as root:
                result = run_script(script, command, *flatten(required_options(command, root)))
                self.assertNotEqual(2, result.returncode, result.stderr)
                expected = MISSING_PROJECTS if command == 'projects' else MISSING_PROJECT
                self.assertIn(expected, result.stdout + result.stderr)

    def test_project_option_is_not_an_abbreviation_of_projects(self):
        for script, command in all_subcommands():
            if command != 'projects':
                continue
            with self.subTest(script=script), tempfile.TemporaryDirectory() as root:
                result = run_script(script, 'projects', '--project', os.path.join(root, 'PP'),
                                    '--output', os.path.join(root, 'out'))
                self.assertEqual(2, result.returncode, result.stderr)

    def test_base_variant_option_is_not_an_abbreviation(self):
        for script, command in all_subcommands():
            if command != 'basevariant':
                continue
            with self.subTest(script=script), tempfile.TemporaryDirectory() as root:
                options = [('--base', value) if name == '--base-variant' else (name, value)
                           for name, value in required_options(command, root)]
                result = run_script(script, command, *flatten(options))
                self.assertEqual(2, result.returncode, result.stderr)

    def test_translation_options_are_accepted(self):
        for script in TRANSLATION_SCRIPTS:
            for command in SUBCOMMAND_SCRIPTS[script]:
                with self.subTest(script=script, command=command), tempfile.TemporaryDirectory() as root:
                    result = run_script(script, command, *flatten(required_options(command, root)),
                                        '--translation-database', os.path.join(root, 'db'),
                                        '--translation-language', 'en_US')
                    self.assertNotEqual(2, result.returncode, result.stderr)

    def test_ecu_variant_option_is_accepted_by_dump_coding(self):
        with tempfile.TemporaryDirectory() as root:
            result = run_script('dumpCoding.py', 'basevariant', *flatten(required_options('basevariant', root)),
                                '--ecu-variant', 'EV_Example')
            self.assertNotEqual(2, result.returncode, result.stderr)

    def test_workspace_and_hexdump_options_are_accepted_by_dump_flash(self):
        for command in SUBCOMMAND_SCRIPTS['dumpFlash.py']:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as root:
                result = run_script('dumpFlash.py', command, *flatten(required_options(command, root)),
                                    '--workspace', os.path.join(root, 'W'), '--hexdump')
                self.assertNotEqual(2, result.returncode, result.stderr)

    def test_single_command_positional_form_is_rejected(self):
        for script, spec in SINGLE_COMMAND_SCRIPTS.items():
            with self.subTest(script=script), tempfile.TemporaryDirectory() as root:
                options = spec['options'](root)
                result = run_script(script, *[value for _, value in options])
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn('the following arguments are required: ' + options[0][0], result.stderr)
                self.assertFalse(os.path.exists(os.path.join(root, 'out')))

    def test_single_command_missing_required_option_is_named(self):
        for script, spec in SINGLE_COMMAND_SCRIPTS.items():
            with self.subTest(script=script), tempfile.TemporaryDirectory() as root:
                options = [pair for pair in spec['options'](root) if pair[0] != spec['omitted']]
                result = run_script(script, *flatten(options))
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn('the following arguments are required: ' + spec['omitted'], result.stderr)

    def test_single_command_named_form_reaches_the_dump(self):
        for script, spec in SINGLE_COMMAND_SCRIPTS.items():
            with self.subTest(script=script), tempfile.TemporaryDirectory() as root:
                result = run_script(script, *flatten(spec['options'](root)))
                self.assertNotEqual(2, result.returncode, result.stderr)
                self.assertIn(spec['missing_folder'], result.stdout + result.stderr)

    def test_single_command_options_are_not_abbreviations(self):
        for script, spec in SINGLE_COMMAND_SCRIPTS.items():
            with self.subTest(script=script), tempfile.TemporaryDirectory() as root:
                options = [(name[:-1], value) if name == spec['omitted'] else (name, value)
                           for name, value in spec['options'](root)]
                result = run_script(script, *flatten(options))
                self.assertEqual(2, result.returncode, result.stderr)

    def test_parse_mwb_translation_options_are_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            result = run_script('parseMWB.py', *flatten(SINGLE_COMMAND_SCRIPTS['parseMWB.py']['options'](root)),
                                '--translation-database', os.path.join(root, 'db'),
                                '--translation-language', 'en_US')
            self.assertNotEqual(2, result.returncode, result.stderr)

    def test_dump_hsqldb_positional_form_is_rejected(self):
        result = run_dump_hsqldb(*[value for _, value in HSQLDB_OPTIONS])
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn('the following arguments are required: --database-folder', result.stderr)

    def test_dump_hsqldb_missing_required_option_is_named(self):
        result = run_dump_hsqldb(*flatten([pair for pair in HSQLDB_OPTIONS if pair[0] != '--output']))
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn('the following arguments are required: --output', result.stderr)

    def test_dump_hsqldb_named_form_reaches_the_dump(self):
        result = run_dump_hsqldb(*flatten(HSQLDB_OPTIONS))
        self.assertNotEqual(2, result.returncode, result.stderr)
        self.assertIn('Input path must be folder', result.stderr)

    def test_dump_hsqldb_options_are_not_abbreviations(self):
        result = run_dump_hsqldb('--database-folder', 'DB', '--database-name', 'name', '--outp', 'out')
        self.assertEqual(2, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
