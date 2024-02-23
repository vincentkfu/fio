#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Copyright 2024 Samsung Electronics Co., Ltd All Rights Reserved
#
# For conditions of distribution and use, see the accompanying COPYING file.
#

"""
# cpuclock.py
#
# Run fio --cpuclock-test many times and summarize results
#
# USAGE
# python3 cpuclock.py [-f fio-executable]
#
# EXAMPLES
# python3 t/cpuclock.py
# python3 t/cpuclock.py -f ./fio
#
# REQUIREMENTS
# Python 3.5+
#
"""

import os
import sys
import time
import argparse
from pathlib import Path
from fiotestlib import FioJobCmdTest, run_fio_tests


class FioCPUClockTest(FioJobCmdTest):
    """fio CPU clock test."""

    def setup(self, parameters):
        """Setup the test."""

        fio_args = [
                    "--cpuclock-test",
                   ]

        super().setup(fio_args)


def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fio', help='path to fio executable (e.g., ./fio)')
    parser.add_argument('-a', '--artifact-root', help='artifact root directory')
    parser.add_argument('-s', '--skip', nargs='+', type=int,
                        help='list of test(s) to skip')
    parser.add_argument('-o', '--run-only', nargs='+', type=int,
                        help='list of test(s) to run, skipping all others')
    parser.add_argument('-t', '--trials', type=int, help='number of trials to run', default=10)
    args = parser.parse_args()

    return args


def main():
    """Run CPU clock tests."""

    args = parse_args()

    if args.fio:
        fio_path = str(Path(args.fio).absolute())
    else:
        fio_path = 'fio'
    print(f"fio path is {fio_path}")

    artifact_root = args.artifact_root if args.artifact_root else \
        f"cpuclock-test-{time.strftime('%Y%m%d-%H%M%S')}"
    os.mkdir(artifact_root)
    print(f"Artifact directory is {artifact_root}")

    test_env = {
              'fio_path': fio_path,
              'fio_root': str(Path(__file__).absolute().parent.parent),
              'artifact_root': artifact_root,
              'basename': 'cpuclock',
              }

    test_list = []
    for i in range(args.trials):
        test_list.append({
            "test_id": i+1,
            "test_class": FioCPUClockTest,
            "fio_opts": {},
            })

    _, failed, _ = run_fio_tests(test_list, test_env, args)
    sys.exit(failed)


if __name__ == '__main__':
    main()
