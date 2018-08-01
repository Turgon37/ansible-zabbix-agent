#!/usr/bin/python

# Inspired by https://github.com/scoopex/zabbix-agent-extensions
# Fetch all block devices name from local host

import argparse
import fcntl
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import re
import stat
import sys

# globals
re_klog_line = re.compile(r"\[\s*(?P<timestamp>\d+\.\d+)\]\s+(?P<message>.*)$")

#
# Tools functions
#

def printError(message):
    """Write an error message into standard error

    Args:
        message : the message to write
    """
    sys.stderr.write('ERROR: {}\n'.format(message))

def printDebug(message):
    """Write a debug message into standard output

    Args:
        message : the message to write
    """
    sys.stdout.write('DEBUG: {}\n'.format(message))

def storeData(data_file_path, data, debug=False):
    """Serialize a python object into a file

    Args:
        data_file_path : the storage file's path
        data : the python data to serialize
        debug : a boolean that enable or not debug
    """
    directory = os.path.dirname(data_file_path)
    if not os.access(directory, os.W_OK):
        printError('unable to write into var directory {}'.format(directory))
        return
    with open(data_file_path, 'wb') as data_handle:
        pickle.dump(data, data_handle)

def readData(data_file_path, fallback=None):
    """Unserialize python object from file

    Args:
        data_file_path : the file from which to read serialized python
        fallback : default object to return on deserialization errors
        debug : a boolean that enable debug mode
    """
    data = fallback
    if os.access(data_file_path, os.R_OK):
        try:
            with open(data_file_path, 'rb') as data_handle:
                data = pickle.load(data_handle)
        except IOError as ex:
           printError('ERROR: unable to read data from file {} : {}'.format(
                 data_file_path,
                 str(ex)))
    return data

def readUptimeSeconds():
    """Read and return current host uptime in seconds

    Returns:
        the uptime in seconds
        None on error
    """
    proc_uptime_path = '/proc/uptime'
    if not os.path.exists(proc_uptime_path):
        printError('ERROR: unable to find uptime from file {}'.format(
                   proc_uptime_path))
        return None

    with open(proc_uptime_path, 'r') as uptime_file:
        raw_uptime = uptime_file.read()
    uptime_parts = raw_uptime.split()
    if len(uptime_parts) != 2:
        printError('ERROR: do not find expected uptime file format')
        return None
    try:
        return float(uptime_parts[0])
    except:
        return None

def parseKernelLog(raw):
    """Parse a raw message from kernel log format

    /dev/kmsg record format:
        facility,sequence,timestamp,[optional,..];message\n

    Args:
        raw : the raw log message as a string
    Returns:
        {level, sequence, timestamp, message} message
        None on format error
    """
    # split line in header and body
    separator_index = raw.find(';')
    if separator_index < 0:
        return None
    header = raw[:separator_index]
    message = raw[separator_index+1:]
    # split header
    raw_level, raw_sequence, raw_timestamp, other = header.split(',')

    try:
        return dict(
            level=int(raw_level),
            sequence=int(raw_sequence),
            timestamp=float(raw_timestamp)/1000000,
            message=message,
        )
    except:
        return None

def parseDmesgLog(raw):
    """


    # [80508.690871] kauditd_printk_skb: 2 callbacks suppressed
    """
    # this regexp describe each line in kernel log
    match = re_klog_line.match(raw)
    if not match:
        return None
    try:
        return dict(
            timestamp=float(match.group('timestamp')),
            message=match.group('message'),
        )
    except:
        return None

#
# command line handler
#
parser = argparse.ArgumentParser(description="Search for block devices connected to this host")
parser.add_argument('--var-directory',
                    help='Directory where to store temporaries informations',
                    action='store',
                    dest='var_directory',
                    default='/var/lib/zabbix')
parser.add_argument('--kernel-log',
                    help='Kernel log pseudo file path',
                    action='store',
                    dest='kernel_log',
                    default='/dev/kmsg')
parser.add_argument('--source-format',
                    help='Choose the source format',
                    action='store',
                    choices=['kmsg', 'dmesg'],
                    dest='source_format',
                    default='kmsg')
parser.add_argument('--filter-older-than',
                    help='do not considers message older than given seconds',
                    action='store',
                    type=int,
                    dest='filter_seconds',
                    default=0)
parser.add_argument('--debug', '-d',
                    help='Output debug information',
                    action='store_true')
args = parser.parse_args()

if args.debug:
    print('Run with {}'.format(str(vars(args))))

#
# init input
#
# detect stdin type
stdin_stats = os.stat('/dev/stdin')
# if this script is run without a pipe
if not stat.S_ISFIFO(stdin_stats.st_mode):
    try:
        with open(args.kernel_log, 'r') as kmsg_file:
            fd = os.dup(kmsg_file.fileno())
    except IOError as ex:
        printError('unable to open kernel log file {} : {}'.format(args.kernel_log, str(ex)))
        sys.exit(1)

    fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
    stream = open(fd)
else:
    stream = sys.stdin

#
# init workflow
#
if args.filter_seconds > 0:
    uptime_seconds = readUptimeSeconds()
    if not uptime_seconds:
        printError('unable to get current uptime')
        sys.exit(1)
    if args.debug:
        printDebug('get current uptime {}'.format(str(uptime_seconds)))

status_file = os.path.join(args.var_directory,
                           'check_dmesg_{}.pickle'.format(os.getuid()))
status_data = dict(last_timestamp=-1)
# load previous status data
if os.path.exists(status_file):
    data_file_mtime = os.stat(status_file).st_mtime
    kernel_log_mtime = os.stat(args.kernel_log).st_mtime
    if kernel_log_mtime < data_file_mtime:
        status_data = readData(status_file, status_data)
        if args.debug:
            printDebug('unserialized object {}'.format(str(status_data)))

total_lines = 0
valid_lines = 0
treated_lines = 0
last_timestamp = status_data['last_timestamp']
if args.source_format == 'kmsg':
    parse_function = parseKernelLog
elif args.source_format == 'dmesg':
    parse_function = parseDmesgLog
else:
    printError('invalid parse format')
    sys.exit(1)


# parse all lines
while True:
    line = stream.readline()
    if not (line):
        break

    total_lines += 1
    message = parse_function(line)
    if not message:
        continue

    valid_lines += 1
    line_timestamp = float(message['timestamp'])
    # ignore line already parsed
    if line_timestamp <= last_timestamp:
        continue

    if (args.filter_seconds > 0 and
        uptime_seconds - line_timestamp > args.filter_seconds):
        continue

    last_timestamp = line_timestamp

    treated_lines += 1


status_data['last_timestamp'] = last_timestamp
storeData(status_file, status_data)
if args.debug:
    printDebug('serialized object {}'.format(str(status_data)))

if args.debug:
    printDebug('treated {} lines on {} parsed valid lines in a total of {} lines'.format(
               treated_lines,
               valid_lines,
               total_lines))
    if valid_lines == 0 and total_lines > 0:
        printDebug('no any line was treated, is source format valid ?')

sys.exit(0)
