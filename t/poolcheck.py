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
