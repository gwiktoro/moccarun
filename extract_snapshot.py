#!/usr/bin/env python3
import argparse
import sys
import logging
import moccalib as ml


def main():
    parser = argparse.ArgumentParser(description='Extract time data from snapshot files')
    parser.add_argument('path', help='Path to the snapshot file')
    parser.add_argument('tsnap_min', type=float, nargs='?', help='Minimum snapshot time')
    parser.add_argument('tsnap_max', type=float, nargs='?', help='Maximum snapshot time (default: 15000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr  # Log to stderr to avoid interfering with CSV output to stdout
    )
    logger = logging.getLogger(__name__)
    
    # Determine tsnap_range based on provided arguments
    if args.tsnap_min is not None:
        tsnap_max = args.tsnap_max if args.tsnap_max is not None else 15000
        tsnap_range = [args.tsnap_min, tsnap_max]
        logger.debug(f"Using tsnap_range: {tsnap_range}")
    else:
        tsnap_range = None
        logger.debug("Using tsnap_range: None (reading entire file)")
    
    logger.debug(f"Reading snapshot file: {args.path}")
    
    ml.extract_snapshot(args.path, tsnap_range=tsnap_range, chunk=10000)

if __name__ == '__main__':
    main()
