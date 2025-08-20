#!/usr/bin/env python3
import argparse
import sys
import moccalib as ml


def main():
    parser = argparse.ArgumentParser(description='Extract time data from snapshot files')
    parser.add_argument('path', help='Path to the snapshot file')
    parser.add_argument('tsnap_min', type=float, nargs='?', help='Minimum snapshot time')
    parser.add_argument('tsnap_max', type=float, nargs='?', help='Maximum snapshot time (default: 15000)')
    
    args = parser.parse_args()
    
    # Determine tsnap_range based on provided arguments
    if args.tsnap_min is not None:
        tsnap_max = args.tsnap_max if args.tsnap_max is not None else 15000
        tsnap_range = [args.tsnap_min, tsnap_max]
    else:
        tsnap_range = None
    
    # Read snapshot data as generator
    snapshot_generator = ml.read_snapshot(args.path, tsnap_range=tsnap_range)
    
    # Handle first dataframe with header
    try:
        first_df = next(snapshot_generator)
        first_df.to_csv(sys.stdout, index=False, header=True)
        
        # Process remaining dataframes without header
        for df in snapshot_generator:
            df.to_csv(sys.stdout, index=False, header=False)
    except StopIteration:
        # No data to process
        pass


if __name__ == '__main__':
    main()
