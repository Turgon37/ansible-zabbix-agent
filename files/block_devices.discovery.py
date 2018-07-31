#!/usr/bin/python

# Inspired by https://github.com/grundic/zabbix-disk-performance
# Fetch all block devices name from local host

import argparse
import json
import os
import re
import sys


# List of device to exclude from results
default_exclude_device_names = ['sr', 'loop', 'ram']
default_sys_block_path = '/sys/class/block'

# CREATE PARSER
parser = argparse.ArgumentParser(description="Search for block devices connected to this host")
parser.add_argument('--exclude',
                    action='append',
                    dest='exclude_device_names',
                    default=default_exclude_device_names,
                    help='Append a device name to the excluded list. Each name is compare with equal test')
parser.add_argument('--exclude-pattern',
                    action='append',
                    dest='exclude_device_names_pattern',
                    default=[],
                    help='Append a device name to the excluded list')
parser.add_argument('--allow-empty',
                    action='store_true',
                    dest='allow_empty',
                    default=False,
                    help='Append empty (zero size) devices to output')
parser.add_argument('--debug', '-d',
                    help='Output debug information',
                    action='store_true')
args = parser.parse_args()

if args.debug:
    print('Run with {}'.format(str(vars(args))))

_exclude_device_names_pattern = map(lambda p: re.compile(p), args.exclude_device_names_pattern)
_exclude_device_names = args.exclude_device_names

devices = []
# Iterate over all block devices, but ignore them if they are in the skippable set
for device_name in os.listdir(default_sys_block_path):
    filename = os.path.join(default_sys_block_path, device_name)
    device = dict(name=device_name, model='UNDEFINED', size=0)
    # consider only symlinks
    if not os.path.islink(filename):
        continue

    if ( any(ignore == device_name for ignore in _exclude_device_names) or
         any(regexp.match(device_name) for regexp in _exclude_device_names_pattern) ):
        continue

    device_model_file = os.path.join(default_sys_block_path,
                                     device_name,
                                     'device/model')
    if os.path.isfile(device_model_file):
        try:
            with open(device_model_file, 'r') as f_model:
                device['model'] = f_model.readline().strip()
        except IOError as ex:
            if args.debug:
                sys.stderr.write('unable to open device model file {} : {}\n',
                                 device_model_file,
                                 str(ex))

    device_size_file = os.path.join(default_sys_block_path, device_name, 'size')
    if os.path.isfile(device_size_file):
        try:
            with open(device_size_file, 'r') as f_size:
                device['size'] = int(f_size.readline().strip())
        except (IOError,ValueError) as ex:
            if args.debug:
                sys.stderr.write('unable to open device size file {} : {}\n',
                                 device_size_file,
                                 str(ex))

        if device['size'] == 0 and not args.allow_empty:
            if args.debug:
                 sys.stderr.write("ignoring device %s, its size is 0\n" % device_name)
            continue

    devices.append(device)

# format data for zabbix
data = map(lambda d: dict(map(lambda x: ("{BLOCKDEVICE"+x[0].upper()+"}", x[1]), d.items())), devices)

# output
if args.debug:
    json.dump({"data": data}, fp=sys.stdout, sort_keys=True, indent=2)
else:
    json.dump({"data": data}, fp=sys.stdout, sort_keys=True)
sys.exit(0)
