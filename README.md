# MOCCALIB repo
by Grzegorz Wiktorowicz

## moccalib.py
main library file. Intended to be included from python scripts/notebooks

Contains helper funcitons for dealing with mocca output files and other.

## moccarun.py
main execution script intended to be a swiss knife for all the functionalities. 
should be linked to PATH directory

## extract_snapshot.py
Script to extract specific snapshots from snapshot.dat files. Can extract multiple snapshots to one file and appends tsnap variable with snapshot time 

## Running multiple moccaruns with `find`

    cmd='cd $0; moccarun $(basename $PWD)_no_new_features --ref-dir . --moccaini '"'"'{"tdelay_fraction": 0.0, "iagb": 0, "rtid_fac": 1.0, "ABBAS_FIX_SUPEDD": 1, "ABBAS_DTINTER_FIX_SEMI": 1, "ABBAS_FIX_GETTB": 1, "tdelay": 0.0}'"'"' --logLevel INFO --dry-run'  # notice how the single quotes were escaped!
    find . -maxdepth 1 -type d -name 'n*' -exec bash -c "$cmd" {} \;

## Load libraries in scripts/notebooks

    sys.path.append('<PATH_TO_MOCCALIB_DIR>')
    import moccalib as ml
