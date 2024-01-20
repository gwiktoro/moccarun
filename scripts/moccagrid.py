#!/usr/bin/env python3

from argparse import ArgumentParser
from pathlib import Path
from shutil import rmtree
import subprocess
import json

from itertools import product

import logging
logging.basicConfig(format='%(asctime)s|%(levelname)s|%(name)s|%(funcName)s|%(lineno)s|%(message)s')
logger = logging.getLogger(__name__)

from moccarun import moccarun

""" TODO

- separate make-path and commit from moccarun() and add as separate functions
- add clever passing of unrecognized arguments to moccarun

"""


def parse_args():

    # Create the argument parser
    parser = ArgumentParser(description=""" Utility for running mocca code

            TODO: add option to test_snapshots 
            """)

    # PATH
    parser.add_argument('grid_path', type=Path, default='.', nargs='?', const='.', help='path to dirrectory for outputs')

    # MOCCA BINARY
    parser.add_argument('--make-path', type=Path, help="Do the code compilation before running the test")
    parser.add_argument('--commit', type=str, default=None, help="Commit for the code to test (will affect the code directory!")
    parser.add_argument('--ref-dir', type=str, default=None, help='Directory with reference files (mocca.ini, mocca.slurm, *nbody.dat)')
    parser.add_argument('--keep-mocca-binary', action='store_true', help='do not overwrite mocca binary file')
    parser.add_argument('--mocca-binary-path', type=Path, default=None, help='path to mocca binary. If not provided parent directories would be searched')

    # GRID
    parser.add_argument('--params-grid', type=json.loads, default={}, help="arguments to change in mocca.ini")

    # SLURM
    parser.add_argument('--user-email', type=str, default='gwiktoro@camk.edu.pl', help='path to dirrectory with mocca.ini')
    parser.add_argument('--partition', type=str, choices=['short','long', 'bigmem'], default=None, help='path to dirrectory with mocca.ini')

    # EXECUTION
    parser.add_argument('--wait', action='store_true', help='wait for simulation to finish (e.g. when used in a pipe)')
    parser.add_argument('--dry-run', action='store_true', help='path to dirrectory with mocca.ini')

    # MISC
    parser.add_argument('--logLevel', action='store', choices=['DEBUG','INFO','WARNING','ERROR'], default='WARNING')

    # Parse the command-line arguments
    args = parser.parse_args()

    return args

def main():

    args = parse_args()

    logger.parent.setLevel(args.logLevel)
    logger.debug(f"{args=}")
    # del args.logLevel  # commented out so the logLevel can be passed to moccarun calls

    # Call the function to execute the bash script

    grid_path = args.grid_path
    grid = args.params_grid
    del args.params_grid
    del args.grid_path
    
    for vals in product(*grid.values()):
        moccaini = dict(zip(grid.keys(), vals))
        print(moccaini)
        
        moccarun(grid_path / '_'.join(f"{k}={v}" for k, v in moccaini.items()).replace(' ', ''),
                moccaini=moccaini,
                **vars(args))

    #moccarun(**vars(args))

if __name__ == '__main__':
    main()





