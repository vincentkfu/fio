#!/usr/bin/python2.7
#
# poolcheck.py
#
# This script processes smalloc debug output from the smalloc-debug branch.
# The debug output looks like this:
#
# smalloc: size=112, pool=0, ptr=0x7f8a6201e6b0, caller=./fio-debug/fio(+0x19176) [0x5596b21e9176], free_blocks=523494
# sfree: pool=0, ptr=0x7f8a6201e6b0, pool->free_blocks=523499
#
# The smalloc-debug branch logs each smalloc() and sfree() call to stderr and
# provides information about the state of the relevant smalloc pools at the
# time of each call. It can be used to check memory consumption and for memory
# leaks.
#
# This script processes the debug output, auditing each smalloc() and sfree()
# call, checking that buffers allocated are not already in use and that buffers
# freed were previously allocated. It also periodically displays a list of
# smalloc callers that hold storage space.
#
# At the very end this script prints out a list of the allocated buffers that
# have not been acted upon by corresponding sfree() calls
#
#
# Usage example:
# ./fio .... |& tee fio-debug-01.log
# python t/poolcheck.py fio-debug-01.log
#

import re
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('source',
            help='fio output file containing smalloc debug prints')
    args = parser.parse_args()

    return args

def display(smalloc, count):
    callers = dict()
    print "count: {0}".format(count)
    for ptr, caller in smalloc.iteritems():
        if caller in callers:
            callers[caller] = callers[caller] + 1
        else:
            callers[caller] = 1
    for caller, count in callers.iteritems():
        print count, caller
    print

def main():
    args = parse_args()

    f = open(args.source, "r")
    flines = f.readlines()
    f.close()

    smalloc = dict()
    trigger = set()
    count = 0
    callregex = re.compile("\(.+\)")

    for line in flines:
        words = line.strip().split(' ')
        if line.find("smalloc") != -1 and line.find("ptr") != -1:
            ptr = words[3].strip(',')[4:]
            if ptr in smalloc:
                print "****ptr={0} already allocated!!!****".format(ptr)
            else:
                caller = callregex.search(words[4]).group(0).strip('()')
                smalloc[ptr] = caller
#                print ptr, caller
            count = count + 1
        elif line.find("sfree") != -1:
            ptr = words[2][4:].strip(',')
            if ptr not in smalloc:
                print "****ptr={0} not found!!!****".format(ptr)
            else:
                del smalloc[ptr]
            count = count - 1
        if count % 3 == 0:
            if count not in trigger:
                trigger.add(count)
                display(smalloc, count)

    for ptr in smalloc:
        print(ptr)
        f = open(args.source, "r")
        flines = f.readlines()
        f.close()
        for line in flines:
            if line.find(ptr) != -1:
                print line.strip()
        print("\n")

if __name__ == "__main__":
    main()
