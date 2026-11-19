import os
import tempfile
import unittest

from flash_export.output import PlainFile
from flash_export.project_files import is_other_project_file, other_project_files


def put(root, relative, content=b'x'):
    path = os.path.join(root, *relative.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as handle:
        handle.write(content)
    return path


class OtherProjectFilesTest(unittest.TestCase):
    def test_rule_selects_only_other_project_files(self):
        selected = ['index.xml', 'rt_index.xml', 'MCD3D_CURR_PROJECT.INI', 'DatabaseVersionInfo.txt',
                    'Common/DVR/ES_X_V001_O.odx', 'Allgemein/Diag.odx-v', 'Common/Topologie/T.xml', 'A/B.XML']
        rejected = ['P.db', 'P.key', 'AStringData.data.gz', 'UStringData.idx', 'SDG_P.dix.gz', 'SDG_P.kix.gz',
                    'ConfigData_X/a.bin', 'A/ConfigData_Y/b.txt', 'Dev/flash-data/c.xml', 'x/flash-data/y/z.sgm',
                    'Java/a.jar', 'Java/b.class', 'FL/DLL/k.dll', 'T/k.EXE', 'project_ext.zip', 'E', 'Jobs/E']
        for path in selected:
            self.assertTrue(is_other_project_file(path), path)
        for path in rejected:
            self.assertFalse(is_other_project_file(path), path)

    def test_files_are_listed_with_project_prefix_in_sorted_order(self):
        with tempfile.TemporaryDirectory() as folder:
            for relative in ('index.xml', 'Common/DVR/b.odx', 'Allgemein/a.odx-v', 'P.db', 'flash-data/x.bin'):
                put(folder, relative)
            files = other_project_files(folder, 'P1')
            self.assertEqual([f.target for f in files],
                             ['P1/Allgemein/a.odx-v', 'P1/Common/DVR/b.odx', 'P1/index.xml'])
            self.assertEqual(files[1].path, os.path.join(folder, 'Common', 'DVR', 'b.odx'))
            self.assertIsInstance(files[0], PlainFile)

    def test_empty_project_gives_no_files(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(other_project_files(folder, 'P1'), [])


if __name__ == '__main__':
    unittest.main()
