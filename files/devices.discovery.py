#!/usr/bin/python

# Inspired by https://github.com/grundic/zabbix-disk-performance
# Fetch all block devices name from local host

import argparse
import json
import os


if __name__ == "__main__":
    # List of device to exclude from results
    exclude_device_names = ['sr', 'loop', 'ram']

    # CREATE PARSER
    parser = argparse.ArgumentParser(description="Search for block devices connected to this host")
    parser.add_argument('--exclude', action='append', dest='exclude_device_names', default=exclude_device_names,
                          help='Append a device name to the excluded list')
    args = parser.parse_args()

    data = []
    # Iterate over all block devices, but ignore them if they are in the skippable set
    for device in os.listdir("/sys/class/block"):
        if not any(ignore in device for ignore in args.exclude_device_names):
            data.append({"{#DEVICENAME}": device})

    # output
    print(json.dumps({"data": data}))
