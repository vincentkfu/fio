#!/usr/bin/env python3
"""
# copy.py
#
# Test the code for fio copy operations
#
# USAGE
# see output from python3 copy.py --help
#
# EXAMPLES
# python3 t/copy_test.py
# python3 t/copy_test.py -f ./fio
#
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path


class FioCopyTest():
    """fio copy test."""

    def __init__(self, artifact_root, test_opts, debug, fio):
        """
        artifact_root   root directory for artifacts (subdirectory will be created under here)
        test            test specification
        """
        self.artifact_root = artifact_root
        self.test_opts = test_opts
        self.debug = debug
        self.fio = fio
        self.filename = None
        self.json_data = None

        self.test_dir = os.path.abspath(os.path.join(self.artifact_root,
                                     f"{self.test_opts['test_id']:03d}"))
        if not os.path.exists(self.test_dir):
            os.mkdir(self.test_dir)

        self.filename = f"copy{self.test_opts['test_id']:03d}"

        if 'returncode' in self.test_opts:
            self.returncode = self.test_opts['returncode']
        else:
            self.returncode = 0

        self.testfilename = os.path.join(self.test_dir, "copy.0.0")
        self.testfilesize = 16*1024*1024

    def precon(self):
        """optional precondition step."""
        return True

    def run_fio(self):
        """Run a test."""

        fio_args = [
            "--name=copy",
            "--group_reporting=1",
            "--randrepeat=0",
            "--norandommap",
            "--rw=copy",
            f"--filename={self.testfilename}",
            f"--output={self.filename}.out",
            f"--ioengine={self.test_opts['ioengine']}",
            f"--output-format={self.test_opts['output-format']}",
        ]
        for opt in ['dest_offset', 'dest_offset_delta', 'io_size',
                    'emulate', 'number_ios', 'bs', 'size', 'runtime',
                    'time_based', 'bsrange', 'bssplit', 'write_iolog']:
            if opt in self.test_opts:
                option = f'--{opt}={self.test_opts[opt]}'
                fio_args.append(option)

        if "passthru" in self.test_opts:
            for opt in self.test_opts['passthru']:
                fio_args.append(opt)

        command = [self.fio] + fio_args
        with open(os.path.join(self.test_dir, f"{self.filename}.command"), "w+") as \
                command_file:
            command_file.write(f"{' '.join(command)}\n")


        passed = True
        stdout_file = open(os.path.join(self.test_dir, f"{self.filename}.stdout"), "w+")
        stderr_file = open(os.path.join(self.test_dir, f"{self.filename}.stderr"), "w+")
        exitcode_file = open(os.path.join(self.test_dir,
                                          f"{self.filename}.exitcode"), "w+")
        try:
            proc = None
            # Avoid using subprocess.run() here because when a timeout occurs,
            # fio will be stopped with SIGKILL. This does not give fio a
            # chance to clean up and means that child processes may continue
            # running and submitting IO.
            proc = subprocess.Popen(command,
                                    stdout=stdout_file,
                                    stderr=stderr_file,
                                    cwd=self.test_dir,
                                    universal_newlines=True)
            proc.communicate(timeout=300)
            exitcode_file.write(f'{proc.returncode}\n')
            passed &= (proc.returncode == self.returncode)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.communicate()
            assert proc.poll()
            print("Timeout expired")
            passed = False
        except Exception:
            if proc:
                if not proc.poll():
                    proc.terminate()
                    proc.communicate()
            print(f"Exception: {sys.exc_info()}")
            passed = False
        finally:
            stdout_file.close()
            stderr_file.close()
            exitcode_file.close()

        if passed:
            if 'json' in self.test_opts['output-format']:
                if not self.get_json():
                    print('Unable to decode JSON data')
                    passed = False

        return passed

    def get_json(self):
        """Convert fio JSON output into a python JSON object"""

        filename = os.path.join(self.test_dir, f"{self.filename}.out")
        with open(filename, 'r') as file:
            file_data = file.read()

        #
        # Sometimes fio informational messages are included at the top of the
        # JSON output, especially under Windows. Try to decode output as JSON
        # data, lopping off up to the first four lines
        #
        lines = file_data.splitlines()
        for i in range(5):
            file_data = '\n'.join(lines[i:])
            try:
                self.json_data = json.loads(file_data)
            except json.JSONDecodeError:
                continue
            else:
                return True

        return False

    @staticmethod
    def check_empty(job):
        """
        Make sure JSON data is empty.

        Some data structures should be empty. This function makes sure that they are.

        job         JSON object that we need to check for emptiness
        """

        return job['total_ios'] == 0 and \
                job['slat_ns']['N'] == 0 and \
                job['clat_ns']['N'] == 0 and \
                job['lat_ns']['N'] == 0

    def check(self):
        """Check test output."""

        raise NotImplementedError()


class TestBasic(FioCopyTest):
    """Test object for Test 1."""

    def precon(self):
        """Create file containing random data."""

        with open(self.testfilename, "wb") as outfile:
            outfile.write(os.urandom(self.testfilesize))

        return True

    def check_ddirs(self):
        """Make sure non-copy ddirs have no data."""

        job = self.json_data['jobs'][0]

        retval = True
        if not self.check_empty(job['read']):
            print("Unexpected read data found in output")
            retval = False
        if not self.check_empty(job['write']):
            print("Unexpected write data found in output")
            retval = False
        if not self.check_empty(job['trim']):
            print("Unexpected trim data found in output")
            retval = False

        return retval

    def check_file_contents(self):
        """First half of file identical to second half."""

        retval = True
        with open(self.testfilename, "rb") as outfile:
            firsthalf = outfile.read(int(self.testfilesize/2))
            secondhalf = outfile.read()
            if firsthalf != secondhalf:
                retval = False
                print("Data mismatch")

        return retval

    def check(self):
        """Check Test 1 output."""

        retval = self.check_ddirs()
        retval &= self.check_file_contents()

        copy = self.json_data['jobs'][0]['copy']
        if copy['io_bytes'] != 8*1024*1024:
            retval = False
            print("io_bytes wrong")
        if copy['io_kbytes'] != 8*1024:
            retval = False
            print("io_kbytes wrong")
        if copy['total_ios'] != 2048:
            retval = False
            print("total_ios != 2048")
        if copy['bw_bytes'] <= 0 or copy['bw'] <= 0 or \
            copy['iops'] <= 0 or copy['runtime'] <= 0 or \
            copy['total_ios'] <= 0:
            retval = False
            print("Rate calculation problem")

        return retval


class Test005(TestBasic):
    """Test object for Test 5."""

    def check(self):
        """Check Test 5 output."""

        retval = self.check_ddirs()
        retval &= self.check_file_contents()

        copy = self.json_data['jobs'][0]['copy']
        if copy['io_bytes'] != 8*1024*1024:
            retval = False
            print("io_bytes wrong")
        if copy['io_kbytes'] != 8*1024:
            retval = False
            print("io_kbytes wrong")
        if copy['total_ios'] != 2:
            retval = False
            print("total_ios != 2")
        if copy['bw_bytes'] <= 0 or copy['bw'] <= 0 or \
            copy['iops'] <= 0 or copy['runtime'] <= 0 or \
            copy['total_ios'] <= 0:
            retval = False
            print("Rate calculation problem")

        return retval


class TestFail(FioCopyTest):
    """Test object for tests that should fail."""

    def check(self):
        """We've already checked that the return code is 1.
        So we don't need to do anything more here."""

        return True


class TestTimeBased(TestBasic):
    """Test object for time_based test."""

    def check_file_contents(self):
        """
        First half of file identical to second half up to amount of data
        copied up to bytes copied
        """

        copy = self.json_data['jobs'][0]['copy']
        bytes = int(copy['io_bytes'])
        if bytes > self.testfilesize / 2:
            bytes = int(self.testfilesize / 2)

        retval = True
        with open(self.testfilename, "rb") as outfile:
            firsthalf = outfile.read(bytes)
            outfile.seek(int(self.testfilesize / 2))
            secondhalf = outfile.read(bytes)
            if firsthalf != secondhalf:
                retval = False
                print("Data mismatch")

        return retval

    def check(self):
        """Check time based test output."""

        retval = self.check_ddirs()
        retval &= self.check_file_contents()

        copy = self.json_data['jobs'][0]['copy']
        if copy['bw_bytes'] <= 0 or copy['bw'] <= 0 or \
            copy['iops'] <= 0 or copy['runtime'] <= 0 or \
            copy['total_ios'] <= 0:
            retval = False
            print("Rate calculation problem")

        return retval


class TestRate(TestTimeBased):
    """Test object for rate test."""

    def delta(self, a, b):
        return abs(a-b) / b > 0.05

    def check(self):
        """Check Test rate test output."""

        retval = self.check_ddirs()
        retval &= self.check_file_contents()

        copy = self.json_data['jobs'][0]['copy']
        if self.delta(copy['bw_bytes'], 128*1024) or \
            self.delta(copy['bw'], 128) or \
            self.delta(copy['iops'], 32):
            retval = False
            print("Rate calculation problem")

        if self.delta(copy['runtime'], 3000):
            retval = False
            print("Runtime problem")

        return retval


class TestBssplit(TestBasic):
    """
    Test object for bssplit tests.
    There is a bug when io_size is used with variable block sizes which allows
    fio to touch more than io_size. Copy 7.5 MiB to avoid overlap between the
    source and destination LBAs so that we will always be able to compare
    source and destination data.
    """

    def __init__(self, artifact_root, test_opts, debug, fio):
        self.check_bytes = int(7.5 * 1024 * 1024)

        super().__init__(artifact_root, test_opts, debug, fio)

    def check_file_contents(self):
        """First half of file identical to second half."""

        retval = True
        with open(self.testfilename, "rb") as outfile:
            firsthalf = outfile.read(self.check_bytes)
            outfile.seek(int(self.testfilesize / 2))
            secondhalf = outfile.read(self.check_bytes)
            if firsthalf != secondhalf:
                retval = False
                print("Data mismatch")

        return retval

    def check_iolog(self):
        """
        Check the iolog to confirm that transfer sizes used come from the list
        of allowed transfer sizes.
        """

        retval = True

        iolog_filename = os.path.join(self.test_dir, "iolog.log")
        with open(iolog_filename, 'r') as log_file:
            for line in log_file:
                tokens = line.split(' ')
                if tokens[2] == 'copy':
                    if int(tokens[4]) not in self.test_opts['test_allowed_bs']:
                        print(f'invalid block size {tokens[4]}')
                        retvak = False
                        break

        return retval

    def check(self):
        """Check bssplit test output."""

        retval = self.check_ddirs()
        retval &= self.check_file_contents()
        retval &= self.check_iolog()

        copy = self.json_data['jobs'][0]['copy']
        delta = copy['io_bytes'] - self.check_bytes
        if delta > max(self.test_opts['test_allowed_bs']):
            retval = False
            print("io_bytes wrong")
        delta = copy['io_kbytes'] - self.check_bytes/1024
        if delta > max(self.test_opts['test_allowed_bs'])/1024:
            retval = False
            print("io_kbytes wrong")
        if copy['bw_bytes'] <= 0 or copy['bw'] <= 0 or \
            copy['iops'] <= 0 or copy['runtime'] <= 0 or \
            copy['total_ios'] <= 0:
            retval = False
            print("Rate calculation problem")

        return retval


def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fio', help='path to file executable (e.g., ./fio)')
    parser.add_argument('-a', '--artifact-root', help='artifact root directory')
    parser.add_argument('-d', '--debug', help='enable debug output', action='store_true')
    parser.add_argument('-s', '--skip', nargs='+', type=int,
                        help='list of test(s) to skip')
    parser.add_argument('-o', '--run-only', nargs='+', type=int,
                        help='list of test(s) to run, skipping all others')
    args = parser.parse_args()

    return args


def main():
    """Run tests of fio copy operations"""

    args = parse_args()

    artifact_root = args.artifact_root if args.artifact_root else \
        f"copy-test-{time.strftime('%Y%m%d-%H%M%S')}"
    os.mkdir(artifact_root)
    print(f"Artifact directory is {artifact_root}")

    if args.fio:
        fio = str(Path(args.fio).absolute())
    else:
        fio = 'fio'
    print(f"fio path is {fio}")

    test_list = [
        {   # simple test copying 8M
            "test_id": 1,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "8M",
            "emulate": 0,
            "test_obj": TestBasic,
        },
        {   # simple test copying 8M with emulation
            "test_id": 2,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "8M",
            "emulate": 1,
            "test_obj": TestBasic,
        },
        {   # simple test copying 8M using dest_offset_delta
            "test_id": 3,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "io_size": "8M",
            "emulate": 0,
            "test_obj": TestBasic,
        },
        {   # simple test copying 8M using dest_offset_delta and emulation
            "test_id": 4,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "io_size": "8M",
            "emulate": 1,
            "test_obj": TestBasic,
        },
        {   # simple test copying 8M using dest_offset_delta and number_ios
            "test_id": 5,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "number_ios": 2,
            "bs": "4M",
            "emulate": 1,
            "test_obj": Test005,
        },
        {   # simple test copying 8M using dest_offset_delta and number_ios
            # check by-ddir parsing for bs
            "test_id": 6,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "number_ios": 2,
            "bs": ",,,4M",
            "emulate": 1,
            "test_obj": Test005,
        },
        {   # make sure copy fails with --readonly option
            "test_id": 7,
            "ioengine": 'psync',
            "output-format": "normal",
            "dest_offset_delta": "8M",
            "number_ios": 2,
            "bs": "1M",
            "emulate": 1,
            "passthru": ["--readonly"],
            "returncode": 1,
            "test_obj": TestFail,
        },
        {   # try running a time_based job
            "test_id": 8,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "3s",
            "size": "8M",
            "test_obj": TestTimeBased,
        },
        {   # try running a time_based job
            # with the rate option
            "test_id": 9,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "3s",
            "size": "8M",
            "passthru": ["--rate=128K"],
            "test_obj": TestRate,
        },
        {   # try running a time_based job
            # with the rate option
            # set via per-data-direction value
            "test_id": 10,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "3s",
            "size": "8M",
            "passthru": ["--rate=,,,128K"],
            "test_obj": TestRate,
        },
        {   # try running a time_based job
            # with the rate_iops option
            "test_id": 11,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "3s",
            "size": "8M",
            "passthru": ["--rate_iops=32"],
            "test_obj": TestRate,
        },
        {   # try running a time_based job
            # with the rate_iops option
            # set via per-data-direction value
            "test_id": 12,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "3s",
            "size": "8M",
            "passthru": ["--rate_iops=,,,32"],
            "test_obj": TestRate,
        },
        {   # try running a time_based job
            # that cannot keep up with the rate_min option
            "test_id": 13,
            "ioengine": 'psync',
            "output-format": "normal",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "10s",
            "size": "8M",
            "passthru": ["--rate_min=100G"],
            "returncode": 1,
            "test_obj": TestFail,
        },
        {   # try running a time_based job
            # that cannot keep up with the rate_min option
            # set via per-data-direction value
            "test_id": 14,
            "ioengine": 'psync',
            "output-format": "normal",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "10s",
            "size": "8M",
            "passthru": ["--rate_min=,,,100G"],
            "returncode": 1,
            "test_obj": TestFail,
        },
        {   # try running a time_based job
            # that cannot keep up with the rate_iops_min option
            "test_id": 15,
            "ioengine": 'psync',
            "output-format": "normal",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "10s",
            "size": "8M",
            "passthru": ["--rate_iops_min=100000000"],
            "returncode": 1,
            "test_obj": TestFail,
        },
        {   # try running a time_based job
            # that cannot keep up with the rate_iops_min option
            # set via per-data-direction value
            "test_id": 16,
            "ioengine": 'psync',
            "output-format": "normal",
            "dest_offset": "8M",
            "time_based": 1,
            "runtime": "10s",
            "size": "8M",
            "passthru": ["--rate_iops_min=,,,100000000"],
            "returncode": 1,
            "test_obj": TestFail,
        },
        {   # test copying 8M
            # use bsrange
            "test_id": 17,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bsrange": "1k-8k",
            "write_iolog": "iolog.log",
            "emulate": 0,
            "test_allowed_bs": [1024, 2048, 3072, 4096, 5120, 6144, 7168, 8192],
            "test_obj": TestBssplit,
        },
        {   # test copying 8M with emulation
            # use bsrange
            "test_id": 18,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bsrange": "1k-8k",
            "write_iolog": "iolog.log",
            "emulate": 1,
            "test_allowed_bs": [1024, 2048, 3072, 4096, 5120, 6144, 7168, 8192],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with single split
            "test_id": 19,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": '4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with per-ddir splits
            "test_id": 20,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": ',4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with per-ddir splits
            "test_id": 21,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": ',,4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with per-ddir splits
            "test_id": 22,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": ',,,4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with per-ddir splits
            "test_id": 23,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": '512/50:2k/50,4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with per-ddir splits
            "test_id": 24,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": '16k/50:8k/50,512/50:24k/50,4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
        {   # simple test copying 8M
            # use bssplit with per-ddir splits
            "test_id": 25,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "7680K",
            "bssplit": '32k/50:8k/50,16k/50:8k/50,512/50:2k/50,4k/50:2k/50',
            "emulate": 0,
            "write_iolog": "iolog.log",
            "test_allowed_bs": [2048, 4096],
            "test_obj": TestBssplit,
        },
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test in test_list:
        if (args.skip and test['test_id'] in args.skip) or \
           (args.run_only and test['test_id'] not in args.run_only):
            skipped = skipped + 1
            outcome = 'SKIPPED (User request)'
        else:
            test_obj = test['test_obj'](artifact_root, test, args.debug, fio)
            status = test_obj.precon()
            if status:
                status = test_obj.run_fio()
            if status:
                status = test_obj.check()
            if status:
                passed = passed + 1
                outcome = 'PASSED'
            else:
                failed = failed + 1
                outcome = 'FAILED'

        print(f"**********Test {test['test_id']} {outcome}**********")

    print(f"{passed} tests passed, {failed} failed, {skipped} skipped")

    sys.exit(failed)


if __name__ == '__main__':
    main()
