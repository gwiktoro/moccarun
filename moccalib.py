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

def get_names_for_detailed_output(write_stm=None):

	if write_stm is None:
		write_stm = """label, idbin, id1, id2, j1, j2, tphys, dtm,                                                                                                     & age, epoch(1),                                                                                                                                         
			 & epoch(2), kstar(1), kstar(2), mass(1), mass(2), sep, ecc,                                                                                              
			 &       rad(1), rad(2), lumin(1), lumin(2), massc(1), massc(2),                                                                                          
			 &       radc(1), radc(2), menv(1), menv(2), renv(1), renv(2),                                                                                            
			 &       ospin(1), ospin(2), dmt(1), dmt(2), dmr(1), dmr(2), rol(1),                                                                                      
			 &       rol(2),dmdt(1), dmdt(2), dm1, dm2 , tb, Lx, Mdot_RLOF, Bi(1), Bi(2)
		"""

	return (re.sub("[^(\w]\d+[^)]", "", write_stm)  # remove line numbers
			 .replace('&', '')  # remove continuation marks
			 .replace(',', ' ')  # use only whitespaces as delimiters
			 .replace('(','_')
			 .replace(')','')
			 .split()
			)

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
                     sep='\s+',
                     chunksize=chunksize,
           )
            
    
    # shifting ndexes to comply with mocca indexes (starting with one)
    # possibly depricated???
    # if names is pd.api.extensions.no_default:
    #     df.columns = df.columns.map(lambda x: x+1)
        
    return df
def read_snapshot(path, tsnap_range=None, chunk_size=10000):
    """Reads snapshot.dat file with memory-efficient chunking
    
    tsnap_range - specifies a range List[2] of snapshot times to read (left inclusive)
    chunk_size - number of rows to process at once (default: 10000)
    """
    
    if tsnap_range is None:
        tsnap_range = [-np.inf, np.inf]
    
    def process_chunk(chunk_data, names, tsnap):
        """Process a chunk of data into DataFrame"""
        if not chunk_data:
            return None
        return (pd.DataFrame(chunk_data, columns=names)
                .assign(tsnap=tsnap)
                .apply(pd.to_numeric, downcast='integer'))
    
    with open(path, 'r') as f:
        names = read_header(path).name.rename(None)
        
        chunk_data = []
        tsnap = None
        
        for line in f:
            if line[0] == '#':  # skip header lines
                continue
                
            if '###' in line:
                # Yield remaining chunk data before starting new snapshot
                if chunk_data and tsnap is not None:
                    df = process_chunk(chunk_data, names, tsnap)
                    if df is not None:
                        yield df
                
                tsnap = float(line.split()[1])
                if tsnap > tsnap_range[1]:
                    # do not process further if found the tsnap is already larger then max
                    return

                chunk_data = []
            else:
                # Only process if within time range
                if tsnap is not None and tsnap_range[0] <= tsnap < tsnap_range[1]:
                    chunk_data.append(line.split())
                    
                    # Yield chunk when it reaches chunk_size
                    if len(chunk_data) >= chunk_size:
                        df = process_chunk(chunk_data, names, tsnap)
                        if df is not None:
                            yield df
                        chunk_data = []
        
        # Yield final chunk
        if chunk_data and tsnap is not None:
            df = process_chunk(chunk_data, names, tsnap)
            if df is not None:
                yield df

def extract_snapshot(snapshot_path, output=sys.stdout, **kwargs):
    """ kwargs passed to read_snapshot """
    # Read snapshot data as generator
    snapshot_generator = read_snapshot(snapshot_path, **kwargs)
    
    # Handle first dataframe with header
    try:
        logger.debug("Processing first dataframe with header")
        first_df = next(snapshot_generator)
        logger.debug(f"First dataframe shape: {first_df.shape}")
        first_df.to_csv(sys.stdout, index=False, header=True)
        
        # Process remaining dataframes without header
        df_count = 1
        for df in snapshot_generator:
            df_count += 1
            logger.debug(f"Processing dataframe {df_count}, shape: {df.shape}")
            df.to_csv(sys.stdout, index=False, header=False)
        
        logger.debug(f"Finished processing {df_count} dataframes")
    except StopIteration:
        logger.debug("No data to process")
        pass

def read_snapshot_old250820(path, tsnap_range=None):
    """Reads snapshot.dat file
    
    tsnap_range - specifies a range List[2] of snapshot times to read (left inclusive)
    """
    
    if tsnap_range is None:
        tsnap_range = [-np.inf, np.inf]
    
    def data_snap2df(data_snap, names, tsnap):
        return (pd.DataFrame(data_snap, 
                    columns=names
                    )
                    .assign(tsnap=tsnap)
                    .apply(pd.to_numeric, downcast='integer')
                )

    with open(path, 'r') as f:

        names = read_header(path).name.rename(None)

        #df_l = []
        data_snap = []
        while line := f.readline():
            if line[0] == '#':  # skipping header lines
                continue
            if '###' in line:
                if len(data_snap)>0:

                    #df_l.append(df)
                    yield data_snap2df(data_snap, names, tsnap)

                tsnap = float(line.split()[1]) 
                data_snap = []
            else:
                if tsnap_range[0]<=tsnap<tsnap_range[1]:
                    data_snap.append(line.split())

        if len(data_snap)>0:

            yield data_snap2df(data_snap, names, tsnap)

#    return (pd.concat(df_l)
#            .apply(pd.to_numeric, downcast='integer')
#            .reset_index(drop=True)
#           )


def to_numeric(s):
    """ avoid deprication error from pd when non-convertable string is provided """
    try:
        return pd.to_numeric(x, downcast='integer')
    except:
        return s

def read_history(path):
    """ reads history files provided through `mm history <id>` 

    Args:
        path (str | Path): path to history-<id>.dat file
    Returns:
        dict: params read from the file header
        pd.DataFrame: history data with attached column names from header
    """
    
    params = {}
    with open(path, 'r') as fp:
        while (line := fp.readline())[0]=='#':
            if (m := re.match("# *(\w+) *= *(\w+)", line)) is not None:
                params[m[1]] = to_numeric(m[2])
            header_line = line
    names = header_line.split()[1:]

    history = pd.read_csv(path, names=names, sep='\s+', comment='#')

    return params, history

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
