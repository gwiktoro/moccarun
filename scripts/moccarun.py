#!/usr/bin/env python3

from copy import copy

from argparse import ArgumentParser
from pathlib import Path
from shutil import rmtree
import subprocess
import json

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

def moccarun(run_path='.', make_path=None, commit=None, ref_dir=None, keep_mocca_binary=False, mocca_binary_path=None, moccaini=None, user_email='gwiktoro@camk.edu.pl', partition=None, wait=False, dry_run=False, **kwargs):

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


    run_path = fix_path(run_path)
    logger.debug(f"{run_path=}")

#    # clean directory except nbody, moccaini and mocca.slurm files
#    logger.info("Cleaning the current directory")
#    files_to_keep = ['single_nbody.dat', 'binary_nbody.dat', 'mocca.slurm', 'mocca.ini']
#    if keep_mocca_binary:
#        files_to_keep.append('mocca')
#    clean_dir(run_path, keep=files_to_keep)

    if not run_path.exists():
        logger.info(f"Creating directory {run_path}")
        if ref_dir is None:
            logger.error(f"Provide reference directory (ref_dir) when creating a new directory!")
            exit(1)
        myrun(f"mkdir -p {run_path}")


    if ref_dir is not None:
        myrun(f"cp -f {ref_dir}/{{mocca.ini,mocca.slurm,*_nbody.dat}} {run_path}")  # '-f' is necessary for overwriting existing files
                                                                                    # othewrise the command fails


    assert (run_path / 'mocca.ini').is_file(), "mocca.ini missing!"
    assert (run_path / 'mocca.slurm').is_file(), "mocca.slurm missing!"
    
    if moccaini is not None:
        sed_cmd = ';'.join(f"s/^{param}\s*=\s*.*/{param} = {value}/" for param, value in moccaini.items())
        myrun(f'sed -i "{sed_cmd}" {run_path/"mocca.ini"}')




    if not keep_mocca_binary:

        logger.info("Copying mocca binary")
        if mocca_binary_path is not None:

            mocca_binary_path = fix_path(mocca_binary_path)
        
        else:
            
            mocca_binary_path = find_mocca_in_parents(run_path)
            # localizing and coping mocca binary
            if mocca_binary_path is None:
                logger.error("mocca binary not found in parent directories! Exiting...")
                exit(1)
        logger.debug(f"{mocca_binary_path=}")

        #(run_path / 'mocca').write_bytes((parent_dir / 'mocca').read_bytes())
        myrun(f"cp {mocca_binary_path} {run_path}")
        
    logger.info("Updating slurm script")
    assert (run_path / 'mocca.slurm').is_file(), "mocca.slurm missing!"
    sed_cmd_l = [
        f"s/#SBATCH -J .*/#SBATCH -J {run_path.name}/",
        f"s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/"
        ]
    if partition is not None:
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
    
    sed_cmd = ';'.join(sed_cmd_l)
    myrun(f'sed -i "{sed_cmd}" {run_path/"mocca.slurm"}')

    if not dry_run:
        myrun(f"(cd {run_path} && sbatch {'--wait' if wait else ''} mocca.slurm)")


def parse_args():

    # Create the argument parser
    parser = ArgumentParser(description=""" Utility for running mocca code

            TODO: add option to test_snapshots 
            """)

    # PATH
    parser.add_argument('run_path', type=Path, default=['.'], nargs='*', help='path to dirrectory with mocca.ini and mocca.slurm')

    # MOCCA BINARY
    parser.add_argument('--make-path', type=Path, help="Do the code compilation before running the test")
    parser.add_argument('--commit', type=str, default=None, help="Commit for the code to test (will affect the code directory!")
    parser.add_argument('--ref-dir', type=str, default=None, help='Directory with reference files (mocca.ini, mocca.slurm, *nbody.dat)')
    parser.add_argument('--keep-mocca-binary', action='store_true', help='path to dirrectory with mocca.ini')
    parser.add_argument('--mocca-binary-path', type=Path, default=None, help='path to mocca binary. If not provided parent directories would be searched')

    # MOCCAINIT
    parser.add_argument('--moccaini', type=json.loads, default={}, help="arguments to change in mocca.ini")

    # SLURM
    parser.add_argument('--user-email', type=str, default='gwiktoro@camk.edu.pl', help='path to dirrectory with mocca.ini')
    parser.add_argument('--partition', type=str, choices=['short','long', 'bigmem'], default=None, help='path to dirrectory with mocca.ini')

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

    # Call the function to execute the bash script
    for rp in args.run_path:
        run_args = copy(args)
        run_args.run_path = rp
        logger.debug(f"{run_args=}")
        moccarun(**vars(run_args))

if __name__ == '__main__':
    main()





