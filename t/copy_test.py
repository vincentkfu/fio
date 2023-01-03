#!/usr/bin/env python3
"""
# copy.py
#
# Test the code for fio copy operations
#
# USAGE
# python3 copy.py [-f fio-path] [-a artifact-root] [--debug]
#
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

    def __init__(self, artifact_root, test_options, debug, fio):
        """
        artifact_root   root directory for artifacts (subdirectory will be created under here)
        test            test specification
        """
        self.artifact_root = artifact_root
        self.test_options = test_options
        self.debug = debug
        self.fio = fio
        self.filename = None
        self.json_data = None

        self.test_dir = os.path.abspath(os.path.join(self.artifact_root,
                                     f"{self.test_options['test_id']:03d}"))
        if not os.path.exists(self.test_dir):
            os.mkdir(self.test_dir)

        self.filename = f"copy{self.test_options['test_id']:03d}"

        if 'returncode' in self.test_options:
            self.returncode = self.test_options['returncode']
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
            f"--filesize={self.testfilesize}",
            f"--filename={self.testfilename}",
            f"--output={self.filename}.out",
            f"--ioengine={self.test_options['ioengine']}",
            f"--output-format={self.test_options['output-format']}",
        ]
        for opt in ['dest_offset', 'dest_offset_delta', 'io_size',
                    'emulate', 'number_ios', 'bs']:
            if opt in self.test_options:
                option = f'--{opt}={self.test_options[opt]}'
                fio_args.append(option)

        if "passthru" in self.test_options:
            for opt in self.test_options['passthru']:
                fio_args.append(opt)

        command = [self.fio] + fio_args
        with open(os.path.join(self.test_dir, f"{self.filename}.command"), "w+") as \
                command_file:
            command_file.write(f"{command}\n")


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
            if 'json' in self.test_options['output-format']:
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


class Test001(FioCopyTest):
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


class Test005(Test001):
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


class Test006(FioCopyTest):
    """Test object for Test 6."""

    def check(self):
        """We've already checked that the return code is 1.
        So we don't need to do anything more here."""

        return True


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
        {
            "test_id": 1,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "8M",
            "emulate": 0,
            "test_obj": Test001,
        },
        {
            "test_id": 2,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset": "8M",
            "io_size": "8M",
            "emulate": 1,
            "test_obj": Test001,
        },
        {
            "test_id": 3,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "io_size": "8M",
            "emulate": 0,
            "test_obj": Test001,
        },
        {
            "test_id": 4,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "io_size": "8M",
            "emulate": 1,
            "test_obj": Test001,
        },
        {
            "test_id": 5,
            "ioengine": 'psync',
            "output-format": "json",
            "dest_offset_delta": "8M",
            "number_ios": 2,
            "bs": "4M",
            "emulate": 1,
            "test_obj": Test005,
        },
        {
            "test_id": 6,
            "ioengine": 'psync',
            "output-format": "normal",
            "dest_offset_delta": "8M",
            "number_ios": 2,
            "bs": "1M",
            "emulate": 1,
            "test_obj": Test006,
            "passthru": ["--readonly"],
            "returncode": 1,
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
