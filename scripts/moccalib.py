"""Helper functions for working with MOCCA output files

v:221129

author: Grzegorz Wiktorowicz
mail:   gwiktoro@camk.edu.pl
"""

import re
import json
import numpy as np
import pandas as pd

import subprocess

import io

import logging
logger = logging.getLogger(__name__)

def read_header(path):
    """Reads header information from system.dat or snapshot.dat
    
    In devel code headers are attached as commented json strings with information about columns
    """
    json_str = ""
    with open(path, 'r') as f:
        while (line := f.readline()).startswith('#'):
            json_str+=line[1:]
    if json_str == "":
        return None
    
    # correcting for rouge characters arfter the last parenthesis (FORTRAN issue)
    json_str = re.sub("(\]|\})[^\}\]]*(\s*)$", "\g<1>\g<2>", json_str)
    
    return pd.DataFrame(json.loads(json_str)).set_index('index')


# def read_system(path):  # DEPRICATED - use read_mocca_file instead
#     return pd.read_csv(path,
#                      names=read_header(path).name,
#                      comment='#',  # skipping header
#                      delim_whitespace=True,  # equivalent to but faster than sep='\s+'
#            )

def read_single_nbody(path):
    """reads single_nbody.dat files"""
    header_names=['sx',  # rescaling factors?
                   'sv',  # rescaling factors?
                   'rvir',  # Virial radius [pc]
                   'Rhtot',  # ??
                   'rtide/rvir'  # rtide - Tidal radius [pc]
                  ]  # from Mcluster/main.c
    header = pd.read_csv(path, sep=' ', nrows=1, names=header_names)
    
    data_names = ['mass', 'x', 'y', 'z', 'vx', 'vy', 'vz', 'epoch', 'Z', 'i+1']
    data = pd.read_csv(path, sep='\t', skiprows=1, names=data_names)
    
    return header, data

def read_binary_nbody(path):
    """reads binary_nbody.dat files"""
    header_names=['sx',  # rescaling factors?
                   'sv',  # rescaling factors?
                   'rvir',  # Virial radius [pc]
                   'Rhtot',  # ??
                   'rtide/rvir'  # rtide - Tidal radius [pc]
                  ]  # from Mcluster/main.c
    header = pd.read_csv(path, sep=' ', nrows=1, names=header_names)
    
    data_names = ['ecc', 'a', 'mass0', 'mass1', 'x', 'y', 'z', 'vx', 'vy', 'vz', 'epoch', 'Z', 'i+1']
    data = pd.read_csv(path, sep='\t', skiprows=1, names=data_names)
    
    return header, data

def read_mocca_file(path, names=None, chunksize=None):

    if names is None:  # try to read header from the datafile
        if (header := read_header(path)) is not None:
            names=header.name.rename(None)
        else:  # if not present, columns will be indexed
               # number of columns is not know beforehand, 
               # so we leave it to pandas and correct 
               # afterwards (see below)
            names=pd.api.extensions.no_default
            
    df = pd.read_csv(path,
                     header=None,
                     names=names,
                     comment='#',  # skipping header
                     delim_whitespace=True,  # equivalent to but faster than sep='\s+'
                     chunksize=chunksize,
           )
            
    
    # shifting ndexes to comply with mocca indexes (starting with one)
    # possibly depricated???
    # if names is pd.api.extensions.no_default:
    #     df.columns = df.columns.map(lambda x: x+1)
        
    return df

def read_snapshot(path, tsnap_range=None):
    """Reads snapshot.dat file
    
    tsnap_range - specifies a range List[2] of snapshot times to read (left inclusive)
    """
    
    if tsnap_range is None:
        tsnap_range = [-np.inf, np.inf]
    
    with open(path, 'r') as f:

        names = read_header(path).name.rename(None)

        df_l = []
        data_snap = []
        while line := f.readline():
            if line[0] == '#':  # skipping header lines
                continue
            if '###' in line:
                if len(data_snap)>0:
                    df = (pd.DataFrame(data_snap, 
                                             columns=names
                                            )
                                .assign(tsnap=tsnap)
                          )

                    df_l.append(df)

                tsnap = float(line.split()[1]) 
                data_snap = []
            else:
                if tsnap_range[0]<=tsnap<tsnap_range[1]:
                    data_snap.append(line.split())

    return (pd.concat(df_l)
            .apply(pd.to_numeric, downcast='integer')
            .reset_index(drop=True)
           )

#### REMOTE COMMANDS

def exec_remotely(cmd, host='chuck', **kwargs):
    
    p=subprocess.run(f"ssh {host} '{cmd}'", shell=True, **kwargs)
    
    return p

def squeue_chuck():
    cmd = 'squeue --format="%.18i %.9P %.128j %.32u %.8T %.20M %.18l %.6D %R" -u gwiktoro'
    p = exec_remotely(cmd, stdout=subprocess.PIPE)

    # removing the quota information
    lines = p.stdout.decode().split('\n')
    for i,line in enumerate(lines):
        if "JOBID" in line:
            break
    else:
        logger.error("Problem running squeue on chuck!")
        
    s = '\n'.join(lines[i:])
    return pd.read_csv(io.StringIO(s), sep='\s+')



# compile new code on chuck
def compile_mocca_remotely(path_to_src, host='chuck'):
    """ Compiles MOCCA code remotely
    
    TODO: use exec_remotely() 
    
    Args:
        path_to_src (str or Path): path on chuck to the MOCCA's src folder.
        host (str): host name on which compile MOCCA (default: chuck)
    Returns:
        subprocess.CompletedProcess
    """
    
    cmd = f'cd {path_to_src} && make clean && make debug'
    
    p = exec_remotely(cmd,
        stdout=subprocess.PIPE,
#        stderr=subprocess.PIPE
    )
    return p

def moccarun_remotely(path_to_test):
    """
    Executes `moccarun` script on chuck
    """
    
    cmd = f"cd {path_to_test} && moccarun"
    
    p = exec_remotely(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    return p  

def compare_snapshots_on_chuck(snapshot0, snapshot1, n_systems=1000):
    
    cmd = f"test_snapshots.py {snapshot0}  {snapshot1} --n-systems={n_systems}"

    p = exec_remotely(cmd)
    
    return p