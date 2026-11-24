import importlib
import os
import subprocess
import sys
import unittest
from unittest import mock

from classes.LongNameTranslation import LongNameTranslation

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LongNameTranslationWithoutJpypeTests(unittest.TestCase):
    def test_modules_import_without_jpype(self):
        with mock.patch.dict(sys.modules, {'jpype': None}):
            for name in ('classes.LongNameTranslation', 'dumpDTC', 'parseMWB', 'dumpFreezeFrames'):
                importlib.reload(importlib.import_module(name))
        # patch.dict restored sys.modules, but the reloaded module objects were changed in place
        for name in ('classes.LongNameTranslation', 'dumpDTC', 'parseMWB', 'dumpFreezeFrames'):
            importlib.reload(importlib.import_module(name))

    def test_translation_without_database_returns_long_name(self):
        with mock.patch.dict(sys.modules, {'jpype': None}):
            self.assertEqual(LongNameTranslation().get_long_name_translation('ID', 'Name'), 'Name')

    def test_translation_with_incomplete_arguments_returns_long_name(self):
        with mock.patch.dict(sys.modules, {'jpype': None}):
            translation = LongNameTranslation('bin/hsqldb.jar', None, 'en_US')
            self.assertEqual(translation.get_long_name_translation('ID', 'Name'), 'Name')

    def test_translation_with_database_but_without_jpype_raises_clear_error(self):
        with mock.patch.dict(sys.modules, {'jpype': None}):
            with self.assertRaisesRegex(RuntimeError, 'JPype1'):
                LongNameTranslation('bin/hsqldb.jar', '/x', 'en_US')

    def test_translation_without_database_leaves_the_jvm_alone(self):
        fake_jpype = mock.MagicMock()
        with mock.patch.dict(sys.modules, {'jpype': fake_jpype}):
            translation = LongNameTranslation()
            translation.__del__()
        fake_jpype.shutdownJVM.assert_not_called()
        fake_jpype.startJVM.assert_not_called()

    def test_dump_hsqldb_without_jpype_exits_with_message(self):
        code = ("import sys; sys.modules['jpype'] = None; "
                "sys.argv = ['dumpHSQLDB.py', '--database-folder', 'a', '--database-name', 'b', '--output', 'c']; "
                "exec(compile(open('dumpHSQLDB.py').read(), 'dumpHSQLDB.py', 'exec'))")
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=REPOSITORY_ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('dumpHSQLDB.py needs the Python package JPype1 (module jpype)', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
