#!/usr/bin/env python3

__VERSION__ = '240508'

import os
import sys
from copy import copy

from argparse import ArgumentParser
from pathlib import Path
from shutil import rmtree
import subprocess
import json

import re

from itertools import product

#import logging
#logging.basicConfig(level='INFO', format='%(asctime)s|%(levelname)s|%(name)s|%(funcName)s|%(lineno)s|%(message)s')
#logger = logging.getLogger(__name__)

from loguru import logger

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


def find_mocca_in_parents(path, require_src_stem=False):

    path = fix_path(path)
    parent_dir = path.parent
    while len(parent_dir.parents)>0:
        if (not require_src_stem or parent_dir.stem == 'src') and (parent_dir / 'mocca').is_file():
            mocca_binary_path = parent_dir / 'mocca'
            break
        parent_dir = parent_dir.parent
    else:
        mocca_binary_path = None

    return mocca_binary_path

def find_mocca_src_path(path):

    path = fix_path(path)
    current = path
    while len(current.parents)>0:
        logger.debug(f'{current=}')
        if current.stem == 'src' and (current / 'mocca-default-2pop.ini').is_file() and (current / 'MOCCA').is_dir() and (current / 'bse').is_dir():
            mocca_src_path = current
            break
        current = current.parent
    else:
        mocca_src_path = None

    return mocca_src_path


def run(cmd, **kwargs):
    """ Run subprocess command
    
    assuming shell=True and capture_output=True if not specified in kwargs

    Args
        cmd (str): command to run
        **kwargs : passed to subprocess.run()
    Returns
        subprocess.CompletedProcess
    """
    if 'shell' not in kwargs.keys():
        kwargs['shell'] = True

    if 'capture_output' not in kwargs.keys():
        kwargs['capture_output'] = True
    
    logger.debug(rf"{cmd=}")
    logger.debug(f"{kwargs=}")
    print(cmd)
    p = subprocess.run(cmd, **kwargs)
    return p

def set_moccaini(path, **kwargs):
    """ make changes to mocca.ini file

    Args:
        path (Path | str): path to mocca.ini file
        kwargs: key and values to update
    """

    path = fix_path(path)
    assert path.is_file(), f"not a file: {path=}"

    for k, v in kwargs.items():
        p = run(rf'grep "^{k}\s*=\s*[^#]\+" {path}')
        if p.returncode == 1:
            logger.error(f"key not found in mocca.ini: {k=}")
            exit(1)
        p_sed = run(rf'sed -i "s/^{k}\s*=\s*.*/{k} = {v}/" {path}')
        assert p_sed.returncode == 0, "sed run incorrectly! {p_sed.args=}"
        logger.info(f"{p.stdout.decode('utf8').strip()} -> {v}")

def set_moccaslurm(path, job_name=None, mail_user=None, partition=None, escape_bin_restart=False):
    """ updates the mocca.slurm file 

    Args:
        path (Path | str): path to mocca.slurm file
    """

    path = fix_path(path)
    assert path.is_file() and path.name == "mocca.slurm", f"Not a mocca slurm file! {path=}"

    sed_cmd_l = []

    if job_name is not None:
        sed_cmd_l.append(f"s/#SBATCH -J .*/#SBATCH -J {job_name}/")
    if mail_user is not None:
        sed_cmd_l.append(f"s/#SBATCH --mail-user=.*/#SBATCH --mail-user={mail_user}/")
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
            logger.error(f"Unsupported partition type! {partition=}")
            exit(1)
    
    if escape_bin_restart:
        sed_cmd_l.append(rf"s/^.\/mocca.*/.\/mocca --escape-bin-restart > zzz-escape-bin-restart/")
    else:
        sed_cmd_l.append(rf"s/^\.\/mocca.*/.\/mocca > zzz/")

    sed_cmd = ';'.join(sed_cmd_l)
    run(f'sed -i "{sed_cmd}" {path}')

def moccarun(path=Path('.'), make_path=None, commit=None, mocca_src_path=None, ref_dir=None, mocca_binary='FIND', moccaini={}, user_email='gwiktoro@camk.edu.pl', partition=None, wait=False, dry_run=False, no_slurm=False, escape_bin_restart=False, moccainipath=None, **kwargs):

    logger.debug(f"Unknown arguments to moccarun(): {kwargs}")

    assert commit is None or (commit is not None and make_path is not None), "make_path has to be provided together with commit"

    # FIXME: use mocca_make for this not raw code
    if make_path is not None:
        cmd = f"(cd {make_path} && "
        if commit is not None:
            cmd += f"git checkout -f {commit} && "
        cmd += "make clean && make debug > /dev/null)"
        p = run(cmd)
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
        run(f"mkdir -p {path}")
        if ref_dir is None:
            mocca_src_path = mocca_src_path or find_mocca_src_path(path)
            assert mocca_src_path is not None, "no path to MOCCA's src/"
            logger.info(f"populating initial files from {mocca_src_path=}")
            run(f"cp -f {mocca_src_path}/mocca-default-2pop.ini {path}/mocca.ini && cp -f {mocca_src_path}/mocca.slurm {path}")
            # TODO copy mocca.ini and mocca.slurm from code dir

    if ref_dir is not None:
        run(f"cp -f {ref_dir}/{{mocca.ini,mocca.slurm,*_nbody.dat}} {path}")  # '-f' is necessary for overwriting existing files
                                                                                    # othewrise the command fails
    if moccainipath is not None:
        run(f"cp -f {moccainipath} {path}")


    set_moccaini(path / 'mocca.ini', **moccaini)
#    assert (path / 'mocca.ini').is_file(), "mocca.ini missing!"
#    
#    if moccaini is not None:
#        sed_cmd = ';'.join(f"s/^{param}\s*=\s*.*/{param} = {value}/" for param, value in moccaini.items())
#        run(f'sed -i "{sed_cmd}" {path/"mocca.ini"}')




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
        p = run(f"cp {mocca_binary_path} {path}")
        if p.returncode != 0:
            logger.error(f"Mocca binary not found in {mocca_binary_path=}")
            exit(1)

    # SLURM
    logger.info("Updating slurm script")

    set_moccaslurm(path / "mocca.slurm", job_name=path.name, mail_user=user_email, partition=partition, escape_bin_restart=escape_bin_restart)

#    sed_cmd_l = [
#        f"s/#SBATCH -J .*/#SBATCH -J {path.name}/",
#        f"s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/"
#        ]
#    if partition is not None:
#        assert (path / 'mocca.slurm').is_file(), "partition provided but mocca.slurm missing!"
#        if partition == 'short':
#            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=36:00:00/")
#            sed_cmd_l.append(f"s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=2999MB/")
#            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p short/")
#        elif partition == 'long':
#            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=336:00:00/")
#            sed_cmd_l.append(f"s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=2999MB/")
#            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p long/")
#        elif partition == 'bigmem':
#            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=168:00:00/")
#            sed_cmd_l.append(f"s/#SBATCH --mem-per-cpu=.*/#SBATCH --mem-per-cpu=5999MB/")
#            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p bigmem/")
#        else:
#            logger.error("Unsupported partition type! Exiting...")
#            exit(1)
#    
#    if (path / 'mocca.slurm').is_file():
#        sed_cmd = ';'.join(sed_cmd_l)
#        run(f'sed -i "{sed_cmd}" {path/"mocca.slurm"}')
#    else:
#        logger.warning('macca.slurm missing!')
#

    # Updating the runmaxcpu parameter for partition
    runmaxcpu_frac = 0.9  # fraction of partitions max time at which the code is gently stopped (for restarts)
    if partition is not None:
        if partition == 'short':
            set_moccaini(path / "mocca.ini", runmaxcpu = int(runmaxcpu_frac * 2160))
        elif partition == 'long':
            set_moccaini(path / "mocca.ini", runmaxcpu = int(runmaxcpu_frac * 20160))
        elif partition == 'bigmem':
            set_moccaini(path / "mocca.ini", runmaxcpu = int(runmaxcpu_frac * 10080))
        else:
            logger.error(f"Unsupported partition type! {partition=}")
            exit(1)


    if not dry_run:
        if no_slurm:
            run(f"(cd {path} && ./mocca > zzz)")
        else:
            p = run(f"(cd {path} && sbatch {'--wait' if wait else ''} mocca.slurm)")
            assert p.returncode == 0, "cannot submit slurm job:\n{p.args=}\n{p.strerr=}"
            logger.info(f"{p.stdout.decode('utf8').strip()}")
    else:
        logger.info("dry run finished")

def make_mocca(path, opts=[]):
    """ Compiles MOCCA code

    Applies changes to internal params if needed 

    CHANGELOG: changes to Mcluster/main.c are no longer needed with the new code

    Args:
        path (Path | str): path to src (see also 'find' option below)
        opts (List[str]): options for compilation
            clean - do cleaning before compilation
            find - find the MOCCA's src directory in upper hierarchy of folders
            small | large - changes params.h to account for small or large memory usage (use only one!)
    """
    available_sizes = {'small', 'large'}  # set of available sizes 
    known_opts = available_sizes | {'find', 'clean'}

    opts = set(opts)
    assert len(unknown_opts := opts - known_opts) < 1, f"Unknown options: {unknown_opts=}"
    
    path = fix_path(path)

    if 'find' in opts:
        path = find_mocca_src_path(path)

    size = len(sizes := {'small','large'}.intersection(opts)) > 0 and sizes.pop() or None
    if size is not None:
        if size == "small":
            MOCCA_params_sed_cmd = rf"s/NMAX=[0-9]\+/NMAX=2200000/;s/NBMAX3=[0-9]\+/NBMAX3=2200000/;s/NSUPZO=[0-9]\+/NSUPZO=400/"
#            MC_main_sed_cmd = f"s/NMAX=[0-9]\+/NMAX=2200000/"
        elif size == "large":
            MOCCA_params_sed_cmd = rf"s/NMAX=[0-9]\+/NMAX=5200000/;s/NBMAX3=[0-9]\+/NBMAX3=5200000/;s/NSUPZO=[0-9]\+/NSUPZO=600/"
#            MC_main_sed_cmd = f"s/int NMAX = [0-9]\+;/int NMAX = 5200000;/"
        else:
            logger.error("wrong value of size in make_mocca(): {size=}")
            exit(0)
        run(f'sed -i "{MOCCA_params_sed_cmd}" {path / "MOCCA/params.h"}')
#       run(f'sed -i "{MC_main_sed_cmd}" {path / "Mcluster/main.c"}')

    cmd = f"(cd {path} &&"
    if 'clean' in opts:
        cmd += " make clean &&"
    cmd += " make debug)"
    run(cmd, capture_output=False)

def parse_args():

    # Create the argument parser
    parser = ArgumentParser(description=f""" Utility for running mocca code

            VERSION: {__VERSION__}

            TODO: add option to test_snapshots 
            """)

    # PATH
    parser.add_argument('paths', type=Path, default=[Path('.')], nargs='*', help='paths to directories with mocca.ini and mocca.slurm')

    parser.add_argument('--grep', type=str, default=None, help='performs grep on MOCCA code files')

    # MOCCA BINARY
    parser.add_argument('--make', type=str, nargs='?', default=None, const='', help="clean,small,large")
    parser.add_argument('--commit', type=str, default=None, help="Commit for the code to test (will affect the code directory!")
    parser.add_argument('--ref-dir', type=str, default=None, help='Directory with reference files (mocca.ini, mocca.slurm, *nbody.dat)')
    parser.add_argument('--moccainipath', type=Path, default=None, help='path to mocca.ini file. Will be copied to simulation directory')
    parser.add_argument('--mocca-binary', action='store', type=str, default='FIND', help="Defines how to obtain the `mocca` binary file. 'FIND' (default) - look for mocca binary in upper directories; 'KEEP' - keep the current `mocca` binary (must be present); otherwise, treated as path to the mocca binary or the folder where it's located")
#    parser.add_argument('--mocca-binary-path', type=Path, default=None, help='path to mocca binary. If not provided parent directories would be searched')

    # MOCCAINIT
    parser.add_argument('--moccaini', type=json.loads, default={}, help="arguments to change in mocca.ini")

    # GRID
    parser.add_argument('--grid', type=str, default=None, help="JSON string defining the simulation's grid")

    # SLURM
    parser.add_argument('--no-slurm', action='store_true', help="do not send slurm job, but execute code normally")
    parser.add_argument('--user-email', type=str, default='gwiktoro@camk.edu.pl', help='user email for slurm notification (default: gwiktoro@camk.edu.pl)')
    parser.add_argument('--partition', type=str, choices=['short','long', 'bigmem'], default=None, help='slurm partition name (default: not change)')

    # EXECUTION
    parser.add_argument('--escape-bin-restart', action='store_true', help='calculate escapers evolution on a calculated simulation')
    parser.add_argument('--wait', action='store_true', help='wait for simulation to finish (e.g. when used in a pipe)')
    parser.add_argument('--dry-run', action='store_true', help='path to dirrectory with mocca.ini')

    # MISC
    parser.add_argument('--logLevel', action='store', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help="set logging level (default WARNING)", default='WARNING')

    # Parse the command-line arguments
    args = parser.parse_args()

    return args

def main():

    args = parse_args()

    logger.remove()
    logger.add(sys.stderr, level=args.logLevel)
    
    #logger.parent.setLevel(args.logLevel)
    logger.debug(f"{args=}")
    del args.logLevel

    print(f'PATHS: {args.paths}')
    print(f'MAKE: {args.make}')


    # Start a grid of simulations
    if args.grid is not None:
        if len(args.paths)!=1:
            logger.error(f"paths must be a sigle Path for '--grid' ({len(args.paths)=})")
            return 1
        grid_path = args.paths[0]
        grid_json = args.grid
        del args.grid
        del args.paths

        try:
            if Path(grid_json).exists():
                with open(grid_json,'r') as fp:
                    grid = json.load(fp)
            else:
                grid = json.loads(grid_json)
        except:
            logger.error(f"Cannot read grid data {grid_json=}")
            return 1
        
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

        if run_args.grep is not None:
            print("GREP")
            path = find_mocca_src_path(run_args.path)
            p = run(rf"""find {path} -type f \( -name "*.f" -o -name "*.f90" -o -name "*.f95" -o -name "*.f03" -o -name "*.f08" -o -name "*.h" \) -print0 | xargs -0 grep -n {run_args.grep} """)
            if p.returncode == 0:
                print(p.stdout.decode('utf8'))
            else:
                print(p.stderr.decode('utf8'))

            continue
        

        if run_args.make is not None:
            logger.debug(f'make: {run_args.make=}')
            make_args = [opt for opt in run_args.make.split(',') if opt != '']
            logger.debug(f'{make_args=}')
            logger.debug(f"{run_args.path=}")
            mocca_src_path = find_mocca_src_path(run_args.path)
            logger.debug(f"{mocca_src_path=}")
            make_mocca(mocca_src_path, opts=make_args)
            #make_mocca(run_args.path, clean=('clean' in make_args), size=(((re_size:=re.search('(small|large)', run_args.make)) is not None) and re_size.group(0) or None), find=('find' in make_args))
            continue  # FIXME  for the current moment I dont allow for make and run at the same time; we need to add looking for the src in the upper folder hierarchy

        moccarun(**vars(run_args))

if __name__ == '__main__':
    main()





