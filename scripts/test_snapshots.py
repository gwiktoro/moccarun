#!/usr/bin/env python3
""" Compares snapshots for testing the refactoring

"""
import numpy as np
import pandas as pd
pd.set_option('display.max_columns', None)
import logging
logging.basicConfig(format='%(asctime)s|%(levelname)s|%(name)s|%(funcName)s|%(lineno)s|%(message)s')
logger=logging.getLogger(__name__)

import moccalib as ml

def smape(y_pred, y_true):
    s0 = np.array(y_true)
    s1 = np.array(y_pred)
    denom = np.abs(s0) + np.abs(s1)
    denom = np.where(denom==0, 1, denom)
    return np.sum(np.abs(s0-s1) / denom) / len(s0) * 200

def compare_cols(df0, df1, cols_to_compare, show=True):
    ret = []
    for col in cols_to_compare:
        s0 = df0[col]
        s1 = df1[col]
        ret.append({'smape':smape(s0, s1) if len(s0) == len(s1) else -1,
                    'mean_0':np.mean(s0),
                    'std_0':np.std(s0),
                    'mean_1':np.mean(s1),
                    'std_1':np.std(s1)
                   })
    ret = pd.DataFrame(ret)
    if show:
        return ret.style.background_gradient(cmap=sns.light_palette("red", as_cmap=True), subset='smape', vmin=0, vmax=200)
    else:
        return ret

def get_system(im, snapshot_refactoring, snapshot_comparison):
    dfim = []
    for df in [snapshot_refactoring, snapshot_comparison]:
        dfim.append(df
              .query(f'im=={im}')
              .set_index('tsnap', drop=True)
              .sort_index()
             )
        
    return tuple(dfim)

if __name__ == "__main__":
    
    import subprocess
    
    from argparse import ArgumentParser
    
    parser = ArgumentParser()
    
    parser.add_argument('--refactoring-snapshot', default='refactoring_snapshot.dat')
    parser.add_argument('--comparison-snapshot', default='comparison_snapshot.dat')
    parser.add_argument('--n-systems', action='store', type=int, default=10, help="number of systems to test")
    parser.add_argument('--download', action='store', default='None', help='what to download download refactoring snapshot', choices=['None','Refactoring','Comparison', 'Both'])
    parser.add_argument('--logLevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='verbosity level for logger')
    args = parser.parse_args()
    
    logger.setLevel(logging.__dict__[args.logLevel])
    
    if args.download in ['Refactoring','Both']:
        logger.info('Downloading snapshot')
        cmd = 'scp camk:/work/chuck/mocca/gwiktoro/mocca-evolv2b-refactoring/src/snapshot.dat refactoring_snapshot.dat'
        print(cmd)
        subprocess.run(cmd, shell=True)
    if args.download in ['Comparison','Both']:
        logger.info('Downloading snapshot')
        cmd = 'scp camk:/work/chuck/mocca/gwiktoro/mocca-evolv2b-comparison/src/snapshot.dat comparison_snapshot.dat'
        print(cmd)
        subprocess.run(cmd, shell=True)
    
    logger.info('Loading snapshots')
    snapshot_refactoring = ml.read_snapshot(args.refactoring_snapshot,
                            tsnap_range=None)
    snapshot_comparison = ml.read_snapshot(args.comparison_snapshot,
                                tsnap_range=None)
    logger.info(f"{snapshot_refactoring.shape=}; {snapshot_comparison.shape=}")
    logger.info(f"{snapshot_refactoring.im.nunique()=}")
    
    cols_to_compare = ['ik1','ik2','sm1','sm2','a','e','mtr1','mtr2']  # TODO add as argument
    
    im_l = np.random.choice(snapshot_refactoring.im.unique(), args.n_systems, replace=False).tolist()
    
    n_comparison_failed = 0
    for im in im_l:
        logger.debug(f"{im=}")
        df_ref, df_comp = get_system(im, snapshot_refactoring, snapshot_comparison)
        logger.debug(f"{im=}; {df_ref.ikb.unique()=}; {df_comp.ikb.unique()=}")
        ret = compare_cols(df_ref, df_comp, cols_to_compare, show=False)
        if not (ret.smape==0).all():
            logger.warning("SMAPE is nonzero!\n" + repr(ret))
            # display(ret)
            n_comparison_failed += 1
            
            
    if n_comparison_failed > 0:
        logger.warning(f"{n_comparison_failed=}")
        exit(1)
    else:
        logger.info("ALL GOOD!")
        exit(0)