import ctypes
import os
import subprocess
import sys
import unittest

from classes import PBL

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DefaultLibraryPathTests(unittest.TestCase):
    def test_default_library_path_on_windows(self):
        self.assertEqual(PBL.default_library_path('/x', 'win32'), os.path.join('/x', 'bin', 'pbl.dll'))

    def test_default_library_path_on_macos(self):
        self.assertEqual(PBL.default_library_path('/x', 'darwin'), os.path.join('/x', 'bin', 'pbl_macos.dylib'))

    def test_default_library_path_on_linux(self):
        self.assertEqual(PBL.default_library_path('/x', 'linux'), os.path.join('/x', 'bin', 'pbl_linux.so'))

    def test_missing_library_raises_file_not_found_naming_the_path(self):
        if sys.platform == 'win32':
            self.skipTest('Windows loads the given path directly')
        missing = os.path.join(REPOSITORY_ROOT, 'no_such_folder', 'bin', 'pbl.dll')
        with self.assertRaises(FileNotFoundError) as context:
            PBL.PBL(missing)
        self.assertIn(os.path.join(REPOSITORY_ROOT, 'no_such_folder', 'bin'), str(context.exception))

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS library only')
    def test_built_library_exports_key_file_functions(self):
        library = ctypes.CDLL(PBL.default_library_path(REPOSITORY_ROOT))
        for name in ('pblKfOpen', 'pblKfClose', 'pblKfGetAbs', 'pblKfGetRel',
                     'pblKfFind', 'pblKfRead', 'pblKfCreate', 'pblKfInsert'):
            self.assertTrue(hasattr(library, name), name)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS library only')
    def test_macos_library_is_universal(self):
        result = subprocess.run(['lipo', '-archs', PBL.default_library_path(REPOSITORY_ROOT)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(set(result.stdout.split()), {'arm64', 'x86_64'})

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS library only')
    def test_pbl_class_loads_library_next_to_given_dll_path(self):
        PBL.PBL(os.path.join(REPOSITORY_ROOT, 'bin', 'pbl.dll'))


if __name__ == '__main__':
    unittest.main()
