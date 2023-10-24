#!/usr/bin/env python3

import json

from pathlib import Path

import argparse
import subprocess

from datetime import datetime

import logging
logging.basicConfig(format='%(asctime)s|%(levelname)s|%(name)s|%(funcName)s|%(lineno)s|%(message)s')
logger = logging.getLogger()

#from . import moccarun
from moccarun import moccarun

def myrun(cmd, **kwargs):

    logger.debug(f"{cmd=}")
    subprocess.run(cmd, shell=True, **kwargs)

def moccatest(test_path, make_path=None, commit=None, ref_path=None, set_moccaini=None, dry_run=False, do_snapshot_test=None, moccarun_kwargs=dict()):
    # Execute the bash script using subprocess module

    cmd_l = []  # list of commands

    test_path = Path(test_path)
    #cmd_l.append(f"mkdir -p {test_path}")
    myrun(f"mkdir -p {test_path}")

    if make_path is not None:
        cmd = f"(cd {make_path} && "
        if commit is not None:
            cmd += f"git checkout -f {commit} && "
        cmd += "make clean && make debug > .make_debug.log"
        myrun(cmd)
#    if compile:
#        cmd_l.append(f"(cd {src_path} && make clean && make debug > /dev/null)")

    #src_path = Path(src_path)

#    if runs_dir is None:
#        runs_dir = src_path / 'run'  # default

#    if test_name is None:
#        test_name = datetime.now().strftime("%y%m%d%H%M%S")
    
#    test_path = runs_dir / test_name
    #test_name = test_path.stem
    
    #if commit is not None:
    #    test_name += f"_{commit}"

    
    if ref_path is not None:
        myrun(f"cp {ref_path}/{{mocca.ini,mocca.slurm,*_nbody.dat}} {test_path}")
        # only change the job name if we copy mocca.slurm from ref_path
#        cmd_l.append(f'sed -i "s/#SBATCH -J .*/#SBATCH -J {test_name}/" {test_path}/mocca.slurm')
#        cmd_l.append(f'sed -i "s/#SBATCH --mail-user=.*/#SBATCH --mail-user={user_email}/" {test_path}/mocca.slurm')
    
    if set_moccaini is not None:
        sed_cmd_l = []
        for param, value in [s.split('=') for s in set_moccaini.replace(' ','').split(',')]:
            sed_cmd_l.append(f"s/{param}\s*=\s*.*/{param} = {value}/")
        sed_cmd = ';'.join(sed_cmd_l)
        myrun('sed -i "{sed_cmd}" {current_dir/"mocca.slurm"}')
#    if run:
#        if do_snapshot_test is not None:
#            cmd_l.append(f'(cd {test_path} && moccarun --wait)')
#            cmd_l.append(f'test_snapshots.py {do_snapshot_test} {test_path / "snapshot.dat"}')
#        else:
#            cmd_l.append(f'(cd {test_path} && moccarun)')

    #cmd = ' && '.join(cmd_l)
    if not dry_run:
        #print(cmd)
        #exit(0)
        moccarun(path=test_path, **moccarun_kwargs)

def parse_args():

    # Create the argument parser
    parser = argparse.ArgumentParser(description="""Test code against another code. 

            TODO: improve help messages below
            """)

    # Add the script_path argument
    parser.add_argument('test_path', type=Path, help='path to the test directory')
    parser.add_argument('--make-path', type=Path, help="Do the code compilation before running the test")
    parser.add_argument('--commit', type=str, default=None, help="Commit for the code to test (will affect the code directory!")
    parser.add_argument('--ref-path', type=str, default=None, help='Directory with reference files (mocca.ini, mocca.slurm, *nbody.dat)')
    parser.add_argument('--set-moccaini', type=str, default=None, help='comma separated list of parameter=value to be set in mocca.ini')
    parser.add_argument('--do-snapshot-test', action='store', type=Path, default=None, help="snapshot.dat path to which the results will be compared")
    parser.add_argument('--dry-run', action='store_true', help="Just print the commands and do nothing")
    parser.add_argument('--moccarun-kwargs', type=json.loads, help="arguments to moccarun as a json string")

    # Parse the command-line arguments
    args = parser.parse_args()

    return args

def main():

    args = parse_args()

    print(args)

    # Call the function to execute the bash script
    #moccatest(args.test_path, src_path=args.src_path, ref_path=args.ref_path, user_email=args.user_email, commit=args.commit, compile=args.compile, set_moccaini=args.set_moccaini, do_snapshot_test=args.do_snapshot_test, dry_run=args.dry_run, run=not args.do_not_run)
    moccatest(**vars(args))
    
if __name__ == '__main__':
    main()
