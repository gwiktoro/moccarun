#!/usr/bin/env python3

from copy import copy

from argparse import ArgumentParser
from pathlib import Path
from shutil import rmtree
import subprocess
import json

import re

from itertools import product

import logging
logging.basicConfig(format='%(asctime)s|%(levelname)s|%(name)s|%(funcName)s|%(lineno)s|%(message)s')
logger = logging.getLogger(__name__)

"""


mv *nbody.dat ..
rm -r ffbonn *.dat *.dump *.80 *.fil *.log *.txt zzz
mv ../*nbody.dat .
cp ../../mocca .
        cmd_l.append(f'sed -i "s/#SBATCH -J .*/#SBATCH -J {test_name}/" {test_path}/mocca.slurm')
        cmd_l.append(f'sed -i "s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/" {test_path}/mocca.slurm')
sbatch $@ mocca.slurm

"""
def fix_path(path):
    """ ensure that the path is Path() class and is absolute """

    return Path(path).absolute()

def clean_dir(path, keep=[]):
    """ Cleans the target directory from all files except those specified in `keep` """

    path = fix_path(path)

    for item in path.iterdir():
        if item.name not in keep:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                rmtree(item)


def find_mocca_in_parents(path):

    path = fix_path(path)
    parent_dir = path.parent
    while len(parent_dir.parents)>0:
        if parent_dir.stem == 'src' and (parent_dir / 'mocca').is_file():
            mocca_binary_path = parent_dir / 'mocca'
            break
        parent_dir = parent_dir.parent
    else:
        mocca_binary_path = None

    return mocca_binary_path

def myrun(cmd, **kwargs):

    logger.debug(f"{cmd=}")
    p = subprocess.run(cmd, shell=True, **kwargs)
    return p

def moccarun(path='.', make_path=None, commit=None, ref_dir=None, mocca_binary='SEARCH', moccaini=None, user_email='gwiktoro@camk.edu.pl', partition=None, wait=False, dry_run=False, no_slurm=False, **kwargs):

    logger.debug(f"Unknown arguments to moccarun(): {kwargs}")

    assert commit is None or (commit is not None and make_path is not None), "make_path has to be provided together with commit"

    if make_path is not None:
        cmd = f"(cd {make_path} && "
        if commit is not None:
            cmd += f"git checkout -f {commit} && "
        cmd += "make clean && make debug > /dev/null)"
        p = myrun(cmd)
        if p.returncode != 0:
            logger.error(f"Compilation failed {p.returncode=}")
            exit(1)


    path = fix_path(path)
    logger.debug(f"{path=}")

#    # clean directory except nbody, moccaini and mocca.slurm files
#    logger.info("Cleaning the current directory")
#    files_to_keep = ['single_nbody.dat', 'binary_nbody.dat', 'mocca.slurm', 'mocca.ini']
#    if keep_mocca_binary:
#        files_to_keep.append('mocca')
#    clean_dir(path, keep=files_to_keep)

    if not path.exists():
        logger.info(f"Creating directory {path}")
        if ref_dir is None:
            logger.error(f"Provide reference directory (ref_dir) when creating a new directory!")
            exit(1)
        myrun(f"mkdir -p {path}")


    if ref_dir is not None:
        myrun(f"cp -f {ref_dir}/{{mocca.ini,mocca.slurm,*_nbody.dat}} {path}")  # '-f' is necessary for overwriting existing files
                                                                                    # othewrise the command fails


    assert (path / 'mocca.ini').is_file(), "mocca.ini missing!"
    
    if moccaini is not None:
        sed_cmd = ';'.join(f"s/^{param}\s*=\s*.*/{param} = {value}/" for param, value in moccaini.items())
        myrun(f'sed -i "{sed_cmd}" {path/"mocca.ini"}')




    if mocca_binary != "KEEP":
        if mocca_binary == 'FIND':

            mocca_binary_path = find_mocca_in_parents(path)
            # localizing and coping mocca binary
            if mocca_binary_path is None:
                logger.error("mocca binary not found in parent directories! Exiting...")
                exit(1)
        else:
            if not mocca_binary.endswith('/mocca'):
                mocca_binary += '/mocca'
            mocca_binary_path = fix_path(mocca_binary)
            
        logger.debug(f"{mocca_binary_path=}")


        #(path / 'mocca').write_bytes((parent_dir / 'mocca').read_bytes())
        p = myrun(f"cp {mocca_binary_path} {path}")
        if p.returncode != 0:
            logger.error(f"Mocca binary not found in {mocca_binary_path=}")
            exit(1)

    # SLURM
    logger.info("Updating slurm script")

    sed_cmd_l = [
        f"s/#SBATCH -J .*/#SBATCH -J {path.name}/",
        f"s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/"
        ]
    if partition is not None:
        assert (path / 'mocca.slurm').is_file(), "partition provided but mocca.slurm missing!"
        if partition == 'short':
            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=36:00:00/")
            sed_cmd_l.append(f"s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=2999MB/")
            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p short/")
        elif partition == 'long':
            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=336:00:00/")
            sed_cmd_l.append(f"s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=2999MB/")
            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p long/")
        elif partition == 'bigmem':
            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=168:00:00/")
            sed_cmd_l.append(f"s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=5999MB/")
            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p bigmem/")
        else:
            logger.error("Unsupported partition type! Exiting...")
            exit(1)
    
    if (path / 'mocca.slurm').is_file():
        sed_cmd = ';'.join(sed_cmd_l)
        myrun(f'sed -i "{sed_cmd}" {path/"mocca.slurm"}')
    else:
        logger.warning('macca.slurm missing!')

    if not dry_run:
        if no_slurm:
            myrun(f"(cd {path} && ./mocca > zzz)")
        else:
            myrun(f"(cd {path} && sbatch {'--wait' if wait else ''} mocca.slurm)")
    else:
        logger.info("dry run finished")

def make_mocca(path, clean=False, size=None):
    """ Compiles MOCCA code

    Applies changes to internal params if needed 

    CHANGELOG: changes to Mcluster/main.c are no longer needed with the new code

    Args:
        size (str): "small", "large" or None (default) - changes params.h and Mcluster/main.c to account for small or large memorry usageg
    """
    if size is not None:
        if size == "small":
            MOCCA_params_sed_cmd = f"s/NMAX=[0-9]\+/NMAX=2200000/;s/NBMAX3=[0-9]+/NBMAX3=2200000/;s/NSUPZO=[0-9]\+/NSUPZO=400/"
#            MC_main_sed_cmd = f"s/NMAX=[0-9]\+/NMAX=2200000/"
        elif size == "large":
            MOCCA_params_sed_cmd = f"s/NMAX=[0-9]\+/NMAX=5200000/;s/NBMAX3=[0-9]+/NBMAX3=5200000/;s/NSUPZO=[0-9]\+/NSUPZO=600/"
#            MC_main_sed_cmd = f"s/int NMAX = [0-9]\+;/int NMAX = 5200000;/"
        else:
            logger.error("wrong value of size in make_mocca(): {size=}")
            exit(0)
        myrun(f'sed -i "{MOCCA_params_sed_cmd}" {path / "MOCCA/params.h"}')
#       myrun(f'sed -i "{MC_main_sed_cmd}" {path / "Mcluster/main.c"}')

    cmd = f"(cd {path} &&"
    if clean:
        cmd += " make clean &&"
    cmd += " make debug)"
    myrun(cmd)

def parse_args():

    # Create the argument parser
    parser = ArgumentParser(description=""" Utility for running mocca code

            TODO: add option to test_snapshots 
            """)

    # PATH
    parser.add_argument('paths', type=Path, default=[Path('.')], nargs='*', help='paths to directories with mocca.ini and mocca.slurm')

    # MOCCA BINARY
    parser.add_argument('--make', type=str, nargs='?', default=None, const='clean', help="clean,small,large")
    parser.add_argument('--commit', type=str, default=None, help="Commit for the code to test (will affect the code directory!")
    parser.add_argument('--ref-dir', type=str, default=None, help='Directory with reference files (mocca.ini, mocca.slurm, *nbody.dat)')
    parser.add_argument('--mocca-binary', action='store', type=str, default='FIND', help="Defines how to obtain the `mocca` binary file. 'FIND' (default) - look for mocca binary in upper directories; 'KEEP' - keep the current `mocca` binary (must be present); otherwise, treated as path to the mocca binary or the folder where it's located")
#    parser.add_argument('--mocca-binary-path', type=Path, default=None, help='path to mocca binary. If not provided parent directories would be searched')

    # MOCCAINIT
    parser.add_argument('--moccaini', type=json.loads, default={}, help="arguments to change in mocca.ini")

    # GRID
    parser.add_argument('--grid', type=json.loads, default=None, help="JSON string defining the simulation's grid")

    # SLURM
    parser.add_argument('--no-slurm', action='store_true', help="do not send slurm job, but execute code normally")
    parser.add_argument('--user-email', type=str, default='gwiktoro@camk.edu.pl', help='user email for slurm notification (default: gwiktoro@camk.edu.pl)')
    parser.add_argument('--partition', type=str, choices=['short','long', 'bigmem'], default=None, help='slurm partition name (default: not change)')

    # EXECUTION
    parser.add_argument('--wait', action='store_true', help='wait for simulation to finish (e.g. when used in a pipe)')
    parser.add_argument('--dry-run', action='store_true', help='path to dirrectory with mocca.ini')

    # MISC
    parser.add_argument('--logLevel', action='store', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='WARNING')

    # Parse the command-line arguments
    args = parser.parse_args()

    return args

def main():

    args = parse_args()

    logger.parent.setLevel(args.logLevel)
    logger.debug(f"{args=}")
    del args.logLevel

    print(f'PATHS: {args.paths}')
    print(f'MAKE: {args.make}')


    # Start a grid of simulations
    if args.grid is not None:
        if len(args.paths)!=1:
            logger.error(f"paths must be a sigle Path for '--grid' (len(paths)={len(args.paths)})")
            return 1
        grid_path = args.paths[0]
        grid = args.grid
        del args.grid
        del args.paths
        
        for vals in product(*grid.values()):
            args.moccaini = dict(zip(grid.keys(), vals))
            print(args.moccaini)
            
            moccarun(grid_path / '_'.join(f"{k}={v}" for k, v in args.moccaini.items()).replace(' ', ''),
                    #moccaini=moccaini,
                    **vars(args))
        return 0


    # Call the function to execute the bash script
    for rp in args.paths:
        run_args = copy(args)
        run_args.path = rp
        logger.debug(f"{run_args=}")

        if run_args.make is not None:
            logger.debug(f'make: {run_args.make=}')
            make_mocca(run_args.path, clean=('clean' in run_args.make), size=(((re_size:=re.search('(small|large)', run_args.make)) is not None) and re_size.group(0) or None))
            continue  # FIXME  for the current moment I dont allow for make and run at the same time; we need to add looking for the src in the upper folder hierarchy

        moccarun(**vars(run_args))

if __name__ == '__main__':
    main()





