#!/usr/bin/env python3
"""
# client-server.py
#
# Test fio's client/server mode.
#
# USAGE
# see python3 client-server.py --help
#
# EXAMPLES
# python3 t/client-server.py 
# python3 t/client-server.py -f ./fio
#
# REQUIREMENTS
# Python 3.6
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
from pathlib import Path
from fiotestlib import FioJobCmdTest, run_fio_tests


PORT_LIST = [
            ",8765",
        ]

PIDFILE_LIST = []

class ClientServerTest(FioJobCmdTest):
    """
    Client/sever test class.
    """

    def setup(self, parameters):
        """Setup a test."""

        fio_args = [
            "--name=client-server",
            "--ioengine=io_uring_cmd",
            "--cmd_type=nvme",
            "--iodepth=8",
            "--iodepth_batch=4",
            "--iodepth_batch_complete=4",
            f"--filename={self.fio_opts['filename']}",
            f"--rw={self.fio_opts['rw']}",
            f"--output={self.filenames['output']}",
            f"--output-format={self.fio_opts['output-format']}",
        ]
        for opt in ['fixedbufs', 'nonvectored', 'force_async', 'registerfiles',
                    'sqthread_poll', 'sqthread_poll_cpu', 'hipri', 'nowait',
                    'time_based', 'runtime', 'verify', 'io_size']:
            if opt in self.fio_opts:
                option = f"--{opt}={self.fio_opts[opt]}"
                fio_args.append(option)

        super().setup(fio_args)


    def check_result(self):
        super().check_result()

TEST_LIST = [
    {
        "test_id": 1,
        "fio_opts": {
            "output-format": "json",
            },
        "test_class": ClientServerTest,
    },
]

def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fio', help='path to file executable (e.g., ./fio)')
    parser.add_argument('-a', '--artifact-root', help='artifact root directory')
    parser.add_argument('-s', '--skip', nargs='+', type=int,
                        help='list of test(s) to skip')
    parser.add_argument('-o', '--run-only', nargs='+', type=int,
                        help='list of test(s) to run, skipping all others')
    args = parser.parse_args()

    return args


def start_servers(fio_path, ports=PORT_LIST):
    """Start servers for our tests."""

    for port in ports:
        tmpfile = tempfile.mktemp()
        cmd = f"sudo {fio_path} --server={port} --daemonize={tmpfile}"
        cmd = cmd.split(' ')
        cmd_result = subprocess.run(cmd, capture_output=True, check=False,
                                   encoding=locale.getpreferredencoding())
        if cmd_result.returncode != 0:
            logging.error("Unable to start server on %s: %s", port, cmd_result.stderr)
            return False

        PIDFILE_LIST.append(tmpfile)

    return True


def stop_servers(pidfiles=PIDFILE_LIST):
    """Stop running fio server invocations."""

    for pidfile in pidfiles:
        with open(pidfile) as file:
            pid = file.read().strip()

        cmd = f"sudo kill {pid}"
        cmd = cmd.split(' ')
        cmd_result = subprocess.run(cmd, capture_output=True, check=False,
                                   encoding=locale.getpreferredencoding())
        if cmd_result.returncode != 0:
            logging.error("Unable to kill server with PID %s: %s", pid, cmd_result.stderr)
            return False

    return True


def main():
    """Run tests for fio's client/server mode."""

    args = parse_args()

    artifact_root = args.artifact_root if args.artifact_root else \
        f"client-server-test-{time.strftime('%Y%m%d-%H%M%S')}"
    os.mkdir(artifact_root)
    print(f"Artifact directory is {artifact_root}")

    if args.fio:
        fio_path = str(Path(args.fio).absolute())
    else:
        fio_path = 'fio'
    print(f"fio path is {fio_path}")

    start_servers(fio_path)
   
    print("Servers started")
    time.sleep(5)

    """
    test_env = {
              'fio_path': fio_path,
              'fio_root': str(Path(__file__).absolute().parent.parent),
              'artifact_root': artifact_root,
              'basename': 'client-server',
              }

    _, failed, _ = run_fio_tests(TEST_LIST, test_env, args)
    sys.exit(failed)
    """

    stop_servers()

if __name__ == '__main__':
    main()
