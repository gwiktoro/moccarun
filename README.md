
# Running multiple moccaruns with `find`

    cmd='cd $0; moccarun $(basename $PWD)_no_new_features --ref-dir . --moccaini '"'"'{"tdelay_fraction": 0.0, "iagb": 0, "rtid_fac": 1.0, "ABBAS_FIX_SUPEDD": 1, "ABBAS_DTINTER_FIX_SEMI": 1, "ABBAS_FIX_GETTB": 1, "tdelay": 0.0}'"'"' --logLevel INFO --dry-run'  # notice how the single quotes were escaped!
    find . -maxdepth 1 -type d -name 'n*' -exec bash -c "$cmd" {} \;

# Load libraries

    sys.path.append('/home/gwiktoro/moccalib/lib/')
    import moccalib as ml
