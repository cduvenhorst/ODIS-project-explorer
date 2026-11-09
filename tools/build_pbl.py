"""Build the universal macOS PBL library (bin/pbl_macos.dylib) from the third_party/pbl submodule."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(ROOT, 'third_party', 'pbl', 'src', 'src')
SOURCES = ['pbl.c', 'pblhash.c', 'pblkf.c']
OUTPUT = os.path.join(ROOT, 'bin', 'pbl_macos.dylib')


def main():
    if sys.platform != 'darwin':
        print('build_pbl.py only runs on macOS.', file=sys.stderr)
        return 1
    sources = [os.path.join(SOURCE_DIR, name) for name in SOURCES]
    missing = [path for path in sources if not os.path.isfile(path)]
    if missing:
        print('PBL sources missing, run: git submodule update --init', file=sys.stderr)
        return 1
    command = ['clang', '-arch', 'arm64', '-arch', 'x86_64', '-mmacosx-version-min=11.0',
               '-shared', '-install_name', '@rpath/pbl_macos.dylib', '-O2', '-fPIC', '-w', '-include', 'stdlib.h', '-include', 'string.h',
               '-I', SOURCE_DIR, '-o', OUTPUT] + sources
    subprocess.run(command, check=True)
    print(f'Built {OUTPUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
