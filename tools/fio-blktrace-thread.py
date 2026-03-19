#!/usr/bin/env python3
"""
# fio-blktrace-thread.py
#
# Generate a fio job file for thread-aware blktrace replay.
#
# USAGE
# See python3 client_server.py --help
#
# EXAMPLES
# blkparse nvme0n1 | python3 fio-blktrace-thread.py
# python3 fio-blktrace-thread.py blkparse-output.log > fio-jobfile.fio
#
#
#
"""
import os
import sys
import time
import locale
import logging
import argparse
import tempfile
import subprocess
import configparser
from pathlib import Path


def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i',
                        help='File countaining output of blkparse')
    parser.add_argument('--output', '-o',
                        help='Filename for fio job file')
    args = parser.parse_args()

    return args


def main():
    """
    Create job file for thread-aware fio blktrace replay.  Scan the output of
    blkparse to determine how many CPUs submitted IOs. Then emit a fio job file
    with one job for each CPU.
    """

    args = parse_args()

    if args.input:
        with open(args.input, "r") as file:
            blkparse = file.read()
    else:
        blkparse = sys.stdin.read()

    blkparse = blkparse.split('\n')
    cpulist = []
    for line in blkparse:
        if line.startswith('CPU'):
            cpu = line.split(' ')[0].replace("CPU", "")
            cpulist.append(cpu)

    output = """
[global]
read_iolog=BLKPARSE_BINARY
"""


    for cpu in cpulist:
        stanza = f"""
[cpu{cpu}]
blktrace_cpu={cpu}
"""
        output += stanza

    if args.output:
        with open(args.output, "w") as file:
            file.write(output)
    else:
        print(output)

if __name__ == '__main__':
    main()
