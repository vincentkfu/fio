#!/usr/bin/env python3
"""
# verify.py
#
# Test fio's verify options.
#
# USAGE
# see python3 verify.py --help
#
# EXAMPLES
# python3 t/verify.py
# python3 t/verify.py --fio ./fio
#
# REQUIREMENTS
# Python 3.6
# - Linux (libaio ioengine)
# - 4 CPUs (test_id 5,6,7)
#
"""
import os
import sys
import time
import logging
import argparse
import platform
import itertools
from pathlib import Path
from fiotestlib import FioJobCmdTest, run_fio_tests
from fiotestcommon import SUCCESS_DEFAULT, SUCCESS_NONZERO, Requirements


VERIFY_OPT_LIST = [
    'direct',
    'iodepth',
    'filesize',
    'bs',
    'time_based',
    'runtime',
    'io_size',
    'offset',
    'number_ios',
    'output-format',
    'directory',
    'norandommap',
    'numjobs',
    'nrfiles',
    'openfiles',
    'cpus_allowed'
    'verify_backlog',
    'verify_backlog_batch',
    'verify_interval',
    'verify_offset',
    'verify_async',
    'verify_async_cpus',
]

class VerifyTest(FioJobCmdTest):
    """
    Verify test class.
    """

    def setup(self, parameters):
        """Setup a test."""

        fio_args = [
            "--name=verify",
            f"--ioengine={self.fio_opts['ioengine']}",
            f"--rw={self.fio_opts['rw']}",
            f"--verify={self.fio_opts['verify']}",
            f"--output={self.filenames['output']}",
        ]
        for opt in VERIFY_OPT_LIST:
            if opt in self.fio_opts:
                option = f"--{opt}={self.fio_opts[opt]}"
                fio_args.append(option)

        if self.fio_opts['verify'] == 'pattern':
            fio_args.append('--verify_pattern="abcd"-120xdeadface')

        super().setup(fio_args)


class VerifyFailureTest(FioJobCmdTest):
    """
    Verify test class. Run a standard verify job, modify the data, and then run
    a verify-only job. Hopefully the last job will show a verification failure.
    """

    @staticmethod
    def add_verify_opts(opt_list, adds):
        """Add optional options."""

        fio_opts = []

        for opt in adds:
            if opt in opt_list:
                option = f"--{opt}={opt_list[opt]}"
                fio_opts.append(option)

        if 'verify' in opt_list and opt_list['verify'] == 'pattern':
            fio_opts.append('--verify_pattern="abcd"-120xdeadface')

        return fio_opts

    def setup(self, parameters):
        """Setup a test."""

        fio_args_base = [
            "--filename=verify",
            "--stonewall",
            f"--ioengine={self.fio_opts['ioengine']}",
        ]

        extra_options = VerifyFailureTest.add_verify_opts(self.fio_opts, VERIFY_OPT_LIST)

        verify = [
            "--verify_only",
            f"--rw={self.fio_opts['rw']}",
            f"--verify={self.fio_opts['verify']}",
        ] + fio_args_base + extra_options


        layout = [
            "--name=layout",
            f"--rw={self.fio_opts['rw']}",
            f"--verify={self.fio_opts['verify']}",
        ] + fio_args_base + extra_options

        success = ["--name=success"] + verify

        mangle = [
            "--name=mangle",
            "--rw=randwrite",
            "--randrepeat=0",
            f"--io_size={self.fio_opts['bs']}",
        ] + fio_args_base + VerifyFailureTest.add_verify_opts(self.fio_opts, ['filesize'])

        failure = ["--name=failure"] + verify

        fio_args = layout + success + mangle + failure + [f"--output={self.filenames['output']}"]
        logging.debug("fio_args: %s", fio_args)

        super().setup(fio_args)

    def check_result(self):
        super().check_result()

        checked = {}

        for job in self.json_data['jobs']:
            if job['jobname'] == 'layout':
                if job['error']:
                    self.passed = False
                    self.failure_reason += " layout job failed"
                checked['layout'] = True
            elif job['jobname'] == 'success':
                if job['error']:
                    self.passed = False
                    self.failure_reason += " first verify pass failed"
                checked['success'] = True
            elif job['jobname'] == 'mangle':
                if job['error']:
                    self.passed = False
                    self.failure_reason += " mangle job failed"
                checked['mangle'] = True
            elif job['jobname'] == 'failure':
                checked['failure'] = True
                if self.fio_opts['verify'] == 'null':
                    continue
                if platform.system() == "Darwin":
                    expected_errno = 92     # macOS EILSEQ
                elif platform.system() == "Windows":
                    expected_errno = 42     # Windows EILSEQ
                else:
                    expected_errno = 84     # Linux EILSEQ
                logging.debug("Error set to %d", expected_errno)
                if job['error'] != expected_errno:
                    self.passed = False
                    self.failure_reason += f" verify job produced {job['error']} instead of errno {expected_errno} Illegal byte sequence"
                    print(self.json_data)
                    with open(self.filenames['stderr'], "r") as se:
                        contents = se.read()
                        print(contents)
            else:
                self.passed = False
                self.failure_reason += " unknown job name"

        if len(checked) != 4:
            self.passed = False
            self.failure_reason += " four phases not completed"

#
# These tests have fixed data directions but can be run for different checksum
# methods.
#
TEST_LIST_DDIR_FIXED = [
    {
        # basic verify job
        "test_id": 1000,
        "fio_opts": {
            "ioengine": "psync",
            "filesize": "1M",
            "bs": 4096,
            "rw": "write",
            "output-format": "json",
            },
        "test_class": VerifyFailureTest,
        "success": SUCCESS_NONZERO,
    },
    {
        # basic test that just random writes data and then verifies it
        "test_id": 1001,
        "fio_opts": {
            "ioengine": "psync",
            "filesize": "1M",
            "bs": 4096,
            "rw": "randwrite",
            "output-format": "json",
            },
        "test_class": VerifyFailureTest,
        "success": SUCCESS_NONZERO,
    },
    {
        # basic libaio seq write test
        "test_id": 1002,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 16,
            "filesize": "1M",
            "bs": 4096,
            "rw": "write",
            "output-format": "json",
            },
        "test_class": VerifyFailureTest,
        "success": SUCCESS_NONZERO,
    },
    {
        # basic libaio rand write test
        "test_id": 1003,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 16,
            "filesize": "1M",
            "bs": 4096,
            "rw": "randwrite",
            "output-format": "json",
            },
        "test_class": VerifyFailureTest,
        "success": SUCCESS_NONZERO,
    },
]

#
# These tests are run for all combinations of data direction and checksum
# methods.
#
TEST_LIST = [
    {
        # basic test
        "test_id": 1,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "2M",
            "bs": 512,
            },
        "test_class": VerifyTest,
    },
    {
        # norandommap
        "test_id": 2,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "2M",
            "norandommap": 1,
            "bs": 512,
            },
        "test_class": VerifyTest,
    },
    {
        # norandommap with verify backlog
        "test_id": 3,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "2M",
            "norandommap": 1,
            "bs": 512,
            "time_based": 1,
            "runtime": 3,
            "verify_backlog": 128,
            "verify_backlog_batch": 64,
            },
        "test_class": VerifyTest,
    },
    {
        # norandommap with verify offset and interval
        "test_id": 4,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "2M",
            "io_size": "4M",
            "norandommap": 1,
            "bs": 4096,
            "verify_interval": 2048,
            "verify_offset": 1024,
            },
        "test_class": VerifyTest,
    },
    {
        # norandommap with verify offload to async threads
        "test_id": 5,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "2M",
            "norandommap": 1,
            "bs": 4096,
            "cpus_allowed": "0-3",
            "verify_async": 2,
            "verify_async_cpus": "0-1",
            },
        "test_class": VerifyTest,
        "requirements":     [Requirements.not_macos,
                             Requirements.cpucount4],
        # mac os does not support CPU affinity
    },
    {
        # tausworthe combine all verify options
        "test_id": 6,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "4M",
            "bs": 4096,
            "cpus_allowed": "0-3",
            "time_based": 1,
            "random_generator": "tausworthe",
            "runtime": 3,
            "verify_interval": 2048,
            "verify_offset": 1024,
            "verify_backlog": 128,
            "verify_backlog_batch": 128,
            "verify_async": 2,
            "verify_async_cpus": "0-1",
            },
        "test_class": VerifyTest,
        "requirements":     [Requirements.not_macos,
                             Requirements.cpucount4],
        # mac os does not support CPU affinity
    },
    {
        # norandommap combine all verify options
        "test_id": 7,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "4M",
            "norandommap": 1,
            "bs": 4096,
            "cpus_allowed": "0-3",
            "time_based": 1,
            "runtime": 3,
            "verify_interval": 2048,
            "verify_offset": 1024,
            "verify_backlog": 128,
            "verify_backlog_batch": 128,
            "verify_async": 2,
            "verify_async_cpus": "0-1",
            },
        "test_class": VerifyTest,
        "requirements":     [Requirements.not_macos,
                             Requirements.cpucount4],
        # mac os does not support CPU affinity
    },
    {
        # multiple jobs and files with verify
        "test_id": 8,
        "fio_opts": {
            "direct": 1,
            "ioengine": "libaio",
            "iodepth": 32,
            "filesize": "512K",
            "nrfiles": 3,
            "openfiles": 2,
            "numjobs": 2,
            "norandommap": 1,
            "bs": 4096,
            "time_based": 1,
            "runtime": 20,
            "verify_interval": 2048,
            "verify_offset": 1024,
            "verify_backlog": 16,
            "verify_backlog_batch": 16,
            },
        "test_class": VerifyTest,
    },
]


def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--fio-root', help='fio root path')
    parser.add_argument('-d', '--debug', help='Enable debug messages', action='store_true')
    parser.add_argument('-f', '--fio', help='path to file executable (e.g., ./fio)')
    parser.add_argument('-a', '--artifact-root', help='artifact root directory')
    parser.add_argument('-c', '--complete', help='Enable all checksums', action='store_true')
    parser.add_argument('-s', '--skip', nargs='+', type=int,
                        help='list of test(s) to skip')
    parser.add_argument('-o', '--run-only', nargs='+', type=int,
                        help='list of test(s) to run, skipping all others')
    parser.add_argument('-k', '--skip-req', action='store_true',
                        help='skip requirements checking')
    args = parser.parse_args()

    return args


def verify_test_csum(test_env, args, csum):
    """
    Adjust test arguments based on values of csum. Then run the tests.
    """
    for test in TEST_LIST_DDIR_FIXED:
        test['force_skip'] = False
        test['fio_opts']['verify'] = csum

        # These tests produce verification failures but not when verify=null,
        # so adjust the success criterion.
        if csum == 'null':
            test['success'] = SUCCESS_DEFAULT
        else:
            test['success'] = SUCCESS_NONZERO

    return run_fio_tests(TEST_LIST_DDIR_FIXED, test_env, args)


def verify_test(test_env, args, ddir, csum):
    """
    Adjust test arguments based on values of ddir and csum.  Then run
    the tests.
    """
    for test in TEST_LIST:
        test['force_skip'] = False

        test['fio_opts']['rw'] = ddir
        test['fio_opts']['verify'] = csum

        # For 100% read data directions we need a file that was written with
        # verify enabled. Use a previous test case for this by telling fio to
        # write to a file in a specific directory.
        if ddir in [ 'read', 'randread' ]:
            directory = os.path.join(test_env['artifact_root'].replace(f'ddir_{ddir}','ddir_write'),
                        f"{test['test_id']:04d}")
            test['fio_opts']['directory'] = str(Path(directory).absolute()) if \
                platform.system() != "Windows" else str(Path(directory).absolute()).replace(':', '\\:')
        else:
            if 'directory' in test['fio_opts']:
                del test['fio_opts']['directory']

    return run_fio_tests(TEST_LIST, test_env, args)


# 100% read workloads below must follow write workloads so that the 100% read
# workloads will be reading data written with verification enabled.
DDIR_LIST = [
        'write',
        'readwrite',
        'read',
        'randwrite',
        'randrw',
        'randread',
             ]
CSUM_LIST1 = [
        'md5',
        'crc64',
        'pattern',
             ]
CSUM_LIST2 = [
        'md5',
        'crc64',
        'crc32c',
        'crc32c-intel',
        'crc16',
        'crc7',
        'xxhash',
        'sha512',
        'sha256',
        'sha1',
        'sha3-224',
        'sha3-384',
        'sha3-512',
        'pattern',
        'null',
             ]

def main():
    """
    Run tests for fio's verify feature.
    """

    args = parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    artifact_root = args.artifact_root if args.artifact_root else \
        f"verify-test-{time.strftime('%Y%m%d-%H%M%S')}"
    os.mkdir(artifact_root)
    print(f"Artifact directory is {artifact_root}")

    if args.fio:
        fio_path = str(Path(args.fio).absolute())
    else:
        fio_path = os.path.join(os.path.dirname(__file__), '../fio')
    print(f"fio path is {fio_path}")

    if args.fio_root:
        fio_root = args.fio_root
    else:
        fio_root = str(Path(__file__).absolute().parent.parent)
    print(f"fio root is {fio_root}")

    if not args.skip_req:
        Requirements(fio_root, args)

    test_env = {
              'fio_path': fio_path,
              'fio_root': str(Path(__file__).absolute().parent.parent),
              'artifact_root': artifact_root,
              'basename': 'verify',
              }

    if platform.system() == 'Linux':
        aio = 'libaio'
        sync = 'psync'
    elif platform.system() == 'Windows':
        aio = 'windowsaio'
        sync = 'sync'
    else:
        aio = 'posixaio'
        sync = 'psync'
    for test in TEST_LIST:
        if 'aio' in test['fio_opts']['ioengine']:
            test['fio_opts']['ioengine'] = aio
        if 'sync' in test['fio_opts']['ioengine']:
            test['fio_opts']['ioengine'] = sync
    for test in TEST_LIST_DDIR_FIXED:
        if 'aio' in test['fio_opts']['ioengine']:
            test['fio_opts']['ioengine'] = aio
        if 'sync' in test['fio_opts']['ioengine']:
            test['fio_opts']['ioengine'] = sync

    total = { 'passed':  0, 'failed': 0, 'skipped': 0 }

    if args.complete:
        csum_list = CSUM_LIST2
    else:
        csum_list = CSUM_LIST1

    try:
        for ddir, csum in itertools.product(DDIR_LIST, csum_list):
            print(f"\nddir: {ddir}, checksum: {csum}")

            test_env['artifact_root'] = os.path.join(artifact_root,
                                                     f"ddir_{ddir}_csum_{csum}")
            os.mkdir(test_env['artifact_root'])

            passed, failed, skipped = verify_test(test_env, args, ddir, csum)

            total['passed'] += passed
            total['failed'] += failed
            total['skipped'] += skipped
    except KeyboardInterrupt:
        pass

    try:
        for csum in csum_list:
            print(f"\nchecksum: {csum}")

            test_env['artifact_root'] = os.path.join(artifact_root,
                                                     f"csum_{csum}")
            os.mkdir(test_env['artifact_root'])

            passed, failed, skipped = verify_test_csum(test_env, args, csum)

            total['passed'] += passed
            total['failed'] += failed
            total['skipped'] += skipped
    except KeyboardInterrupt:
        pass

    print(f"\n\n{total['passed']} test(s) passed, {total['failed']} failed, " \
            f"{total['skipped']} skipped")
    sys.exit(total['failed'])


if __name__ == '__main__':
    main()
