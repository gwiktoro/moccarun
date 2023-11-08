#!/usr/bin/env python3

from argparse import ArgumentParser
from pathlib import Path
import subprocess

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

def moccarun(run_path='.', mocca_binary_path=None, keep_mocca_binary=False, user_email='gwiktoro@camk.edu.pl', partition=None, dry_run=False, wait=False, **kwargs):


    logger.debug(f"Unknown arguments to moccarun(): {kwargs}")

    run_path = Path(run_path).absolute()
    logger.debug(f"{run_path=}")

    # clean directory except nbody, moccaini and mocca.slurm files
    logger.info("Cleaning the current directory")
    files_to_keep = ['single_nbody.dat', 'binary_nbody.dat', 'mocca.slurm', 'mocca.ini']  # mocca.ini MUST be last on this list
    if keep_mocca_binary:
        files_to_keep.append('mocca')

#    tmp = '\|'.join(files_to_keep)
#    cmd = rf"shopt -s extglob; rm -rf !\({tmp}\)"
    cmd = f"(cd {run_path} && mkdir -p .moccarun_tmp && for file in {' '.join(files_to_keep)}; do [ -e $file ] && mv $file .moccarun_tmp; done && rm -rf * && mv .moccarun_tmp/* . && rmdir .moccarun_tmp)"
    logger.debug(f"{cmd=}")
    subprocess.run(cmd, shell=True, executable='/bin/bash')

    assert (run_path / 'mocca.ini').is_file(), "mocca.ini missing!"
    


    if not keep_mocca_binary:

        logger.info("Copying mocca binary")
        if mocca_binary_path is not None:

            mocca_binary_path = Path(mocca_binary_path)
        
        else:
            
            # localizing and coping mocca binary
            parent_dir = run_path.parent
            while len(parent_dir.parents)>0:
                if parent_dir.stem == 'src' and (parent_dir / 'mocca').is_file():
                    mocca_binary_path = parent_dir / 'mocca'
                    break
                parent_dir = parent_dir.parent
            else:
                logger.error("mocca binary not found in parent directories! Exiting...")
                exit(1)

        logger.debug(f"{mocca_binary_path=}")
        #(run_path / 'mocca').write_bytes((parent_dir / 'mocca').read_bytes())
        cmd = f"cp {parent_dir / 'mocca'} {run_path / 'mocca'}"
        logger.debug(f"{cmd=}")
        subprocess.run(cmd, shell=True)
        
    logger.info("Updating slurm script")
    assert (run_path / 'mocca.slurm').is_file(), "mocca.slurm missing!"
    sed_cmd_l = [
        f"s/#SBATCH -J .*/#SBATCH -J {run_path.stem}/",
        f"s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/"
        ]
    if partition is not None:
        if partition == 'short':
            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=36:00:00/")
            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p short/")
        elif partition == 'long':
            sed_cmd_l.append(f"s/#SBATCH --time=.*/#SBATCH --time=336:00:00/")
            sed_cmd_l.append(f"s/#SBATCH -p .*/#SBATCH -p long/")
        else:
            logger.error("Unsupported partition type! Exiting...")
            exit(1)
    
    sed_cmd = ';'.join(sed_cmd_l)
    cmd = f'sed -i "{sed_cmd}" {run_path/"mocca.slurm"}'
    logger.debug(f"{cmd=}")
    subprocess.run(cmd, shell=True)

    if not dry_run:
        cmd = f"(cd {run_path} && sbatch {'--wait' if wait else ''} mocca.slurm)"
        logger.debug(f"{cmd=}")
        subprocess.run(cmd, shell=True)


def parse_args():

    # Create the argument parser
    parser = ArgumentParser(description="""Test code against another code. 

            TODO: improve help messages below
            """)

    # Add the script_path argument
    parser.add_argument('path', type=Path, default='.', nargs='?', const='.', help='path to dirrectory with mocca.ini and mocca.slurm')
    parser.add_argument('--mocca-binary-path', type=Path, default=None, help='path to mocca binary. If not provided parent directories would be searched')
    parser.add_argument('--user-email', type=str, default='gwiktoro@camk.edu.pl', help='path to dirrectory with mocca.ini')
    parser.add_argument('--partition', type=str, choices=['short','long'], default=None, help='path to dirrectory with mocca.ini')
    parser.add_argument('--dry-run', action='store_true', help='path to dirrectory with mocca.ini')
    parser.add_argument('--logLevel', action='store', choices=['DEBUG','INFO','WARNING','ERROR'], default='WARNING')
    parser.add_argument('--keep-mocca-binary', action='store_true', help='path to dirrectory with mocca.ini')
    parser.add_argument('--wait', action='store_true', help='wait for simulation to finish (e.g. when used in a pipe)')

    # Parse the command-line arguments
    args = parser.parse_args()

    return args

def main():

    args = parse_args()

    logger.parent.setLevel(args.logLevel)
    logger.debug(f"{args=}")
    del args.logLevel

    # Call the function to execute the bash script
    moccarun(**vars(args))

if __name__ == '__main__':
    main()





