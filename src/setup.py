from distutils.core import setup
import py2exe
import numpy
import os
import sys

# add any numpy directory containing a dll file to sys.path
def numpy_dll_paths_fix():
    paths = set()
    np_path = numpy.__path__[0]
    for dirpath, _, filenames in os.walk(np_path):
        for item in filenames:
            if item.endswith('.dll'):
                paths.add(dirpath)

    sys.path.append(*list(paths))

numpy_dll_paths_fix()

setup(console=['dat_unpack.py'],
      options={"py2exe": {"compressed": 1, "optimize": 2, "bundle_files": 1}},
      zipfile=None)

setup(console=['wmb_parser.py'],
      options={"py2exe": {"compressed": 1, "optimize": 2, "bundle_files": 1}},
      zipfile=None)