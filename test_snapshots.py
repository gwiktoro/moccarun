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
    
    parser.add_argument('snapshot0')
    parser.add_argument('snapshot1')
    parser.add_argument('--n-systems', action='store', type=int, default=None, help="number of systems to test")
    parser.add_argument('--logLevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='verbosity level for logger')
    args = parser.parse_args()
    
    logger.setLevel(logging.__dict__[args.logLevel])
    
    logger.info('Loading snapshots')
    snapshot0 = ml.read_snapshot(args.snapshot0,
                            tsnap_range=None)
    snapshot1 = ml.read_snapshot(args.snapshot1,
                                tsnap_range=None)
    logger.info(f"{snapshot0.shape=}; {snapshot1.shape=}")
    logger.info(f"{snapshot0.im.nunique()=}")
    
    cols_to_compare = ['ik1','ik2','sm1','sm2','a','e','mtr1','mtr2']  # TODO add as argument
    logger.debug(f"{cols_to_compare=}")
    
    im_all = snapshot0.im.unique()
    if args.n_systems is None:
        im_l = im_all.tolist()  #snapshot_refactoring.im.unique().tolist()
    else:
        im_l = np.random.choice(im_all, min(args.n_systems, len(im_all)), replace=False).tolist()
    logger.info(f"{len(im_l)=}")
    
    n_comparison_failed = 0
    for im in im_l:
        logger.debug(f"{im=}")
        df0, df1 = get_system(im, snapshot0, snapshot1)
        logger.debug(f"{im=}; {df0.ikb.unique()=}; {df1.ikb.unique()=}")
        ret = compare_cols(df0, df1, cols_to_compare, show=False)
        if not (ret.smape==0).all():
            logger.warning("SMAPE is nonzero!\n" + repr(ret))
            # display(ret)
            n_comparison_failed += 1
            
            
    if n_comparison_failed > 0:
        logger.warning(f"{n_comparison_failed=} ({n_comparison_failed/len(im_l) * 100:.2f}%)")
        exit(1)
    else:
        logger.info("ALL GOOD!")
        exit(0)
