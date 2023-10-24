#!/usr/bin/env python3

from argparse import ArgumentParser
from pathlib import Path
import subprocess

import logging
logging.basicConfig(format='%(asctime)s|%(levelname)s|%(name)s|%(funcName)s|%(lineno)s|%(message)s')
logger = logging.getLogger()

"""


mv *nbody.dat ..
rm -r ffbonn *.dat *.dump *.80 *.fil *.log *.txt zzz
mv ../*nbody.dat .
cp ../../mocca .
        cmd_l.append(f'sed -i "s/#SBATCH -J .*/#SBATCH -J {test_name}/" {test_path}/mocca.slurm')
        cmd_l.append(f'sed -i "s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/" {test_path}/mocca.slurm')
sbatch $@ mocca.slurm

"""

def moccarun(path='.', mocca_binary_path=None, keep_mocca_binary=False, user_email='gwiktoro@camk.edu.pl', partition=None, dry_run=False, wait=False):

    # clean directory except nbody, moccaini and mocca.slurm files
    logger.info("Cleaning the current directory")
    files_to_keep = ['mocca.ini', 'mocca.slurm', 'single_nbody.dat', 'binary_nbody.dat']
    if keep_mocca_binary:
        files_to_keep.append('mocca')

#    tmp = '\|'.join(files_to_keep)
#    cmd = rf"shopt -s extglob; rm -rf !\({tmp}\)"
    cmd = f"mkdir -p .moccarun_tmp && mv {' '.join(files_to_keep)} .moccarun_tmp && rm -rf * && cp .moccarun_tmp/* . && rm -rf .moccarun_tmp"
    logger.debug(f"{cmd=}")
    subprocess.run(cmd, shell=True, executable='/bin/bash')

    current_dir = Path(path).absolute()
    logger.debug(f"{current_dir=}")
    if not keep_mocca_binary:

        logger.info("Copying mocca binary")
        if mocca_binary_path is not None:

            mocca_binary_path = Path(mocca_binary_path)
        
        else:
            
            # localizing and coping mocca binary
            parent_dir = current_dir.parent
            while len(parent_dir.parents)>0:
                if parent_dir.stem == 'src' and (parent_dir / 'mocca').is_file():
                    mocca_binary_path = parent_dir / 'mocca'
                    break
                parent_dir = parent_dir.parent
            else:
                logger.error("mocca binary not found in parent directories! Exiting...")
                exit(1)

        logger.debug(f"{mocca_binary_path=}")
        #(current_dir / 'mocca').write_bytes((parent_dir / 'mocca').read_bytes())
        cmd = f"cp {parent_dir / 'mocca'} {current_dir / 'mocca'}"
        logger.debug(f"{cmd=}")
        subprocess.run(cmd, shell=True)
        
    logger.info("Updating slurm script")
    sed_cmd_l = [
        f"s/#SBATCH -J .*/#SBATCH -J {current_dir.stem}/",
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
    cmd = f'sed -i "{sed_cmd}" {current_dir/"mocca.slurm"}'
    logger.debug(f"{cmd=}")
    subprocess.run(cmd, shell=True)

    if not dry_run:
        cmd = f"sbatch {'--wait' if wait else ''} mocca.slurm"
        logger.debug(f"{cmd=}")
        subprocess.run(cmd, shell=True)


def parse_args():

    # Create the argument parser
    parser = ArgumentParser(description="""Test code against another code. 

            TODO: improve help messages below
            """)

    # Add the script_path argument
    parser.add_argument('--path', type=Path, default='.', help='path to dirrectory with mocca.ini and mocca.slurm')
    parser.add_argument('--mocca-binary-path', type=Path, default=None, help='path to mocca binary. If not provided parent directories would be searched')
    parser.add_argument('--user-email', type=str, default='gwiktoro@camk.edu.pl', help='path to dirrectory with mocca.ini')
    parser.add_argument('--partition', type=str, choices=['short','long'], default=None, help='path to dirrectory with mocca.ini')
    parser.add_argument('--dry-run', action='store_true', help='path to dirrectory with mocca.ini')
    parser.add_argument('--logLevel', action='store', choices=['DEBUG','INFO','WARNING','ERROR'], default='WARNING')
    parser.add_argument('--keep-mocca-binary', action='store_true', help='path to dirrectory with mocca.ini')

    # Parse the command-line arguments
    args = parser.parse_args()

    return args

def main():

    args = parse_args()

    logger.setLevel(args.logLevel)
    logger.debug(f"{args=}")

    # Call the function to execute the bash script
    moccarun(path=args.path, mocca_binary_path=args.mocca_binary_path, keep_mocca_binary=args.keep_mocca_binary, user_email=args.user_email, partition=args.partition, dry_run=args.dry_run)

if __name__ == '__main__':
    main()





