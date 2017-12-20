#!/usr/bin/python

# Inspired by https://github.com/grundic/zabbix-disk-performance
# Fetch all block devices name from local host

import argparse
import json
import os
import re


if __name__ == "__main__":
    # List of device to exclude from results
    exclude_device_names = ['sr', 'loop', 'ram']
    exclude_device_names_pattern = []

    # CREATE PARSER
    parser = argparse.ArgumentParser(description="Search for block devices connected to this host")
    parser.add_argument('--exclude', action='append', dest='exclude_device_names', default=exclude_device_names,
                          help='Append a device name to the excluded list. Each name is compare with host devices names\' using substring test')
    parser.add_argument('--exclude-pattern', action='append', dest='exclude_device_names_pattern', default=None,
                          help='Append a device name to the excluded list')
    args = parser.parse_args()

    if args.exclude_device_names_pattern:
        for pattern in args.exclude_device_names_pattern:
            exclude_device_names_pattern.append(re.compile(pattern))

    data = []
    # Iterate over all block devices, but ignore them if they are in the skippable set
    for device in os.listdir("/sys/class/block"):
        if ( not any(ignore in device for ignore in args.exclude_device_names) and
              not any(regexp.match(device) for regexp in exclude_device_names_pattern) ):
            data.append({"{#DEVICENAME}": device})

    # output
    print(json.dumps({"data": data}))
