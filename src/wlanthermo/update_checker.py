#!/usr/bin/env python3
# coding=utf-8

# update_checker.py - Checks if system update is available
#
# This is free and unencumbered software released into the public domain.

# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.

# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# For more information, please refer to <http://unlicense.org/>

import argparse
import subprocess
import re
import json


def check_updates(packages):
    results = dict()
    process = subprocess.run(
        'LANG=C apt-get -su dist-upgrade',
        stdout=subprocess.PIPE,
        shell=True)
    output = process.stdout.decode('utf-8')
    counts = re.search(
        '''^(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded.''',
        output,
        re.MULTILINE)
    updatecount = int(counts.group(1)) + int(counts.group(2))
    all_updates = updatecount
    for package in args.package:
        packageinfo = re.search('^Inst {package} \[(\S*)\] \((\S+)'.format(package=package),
        output,
        re.MULTILINE)
        if packageinfo is None:
            results[package] = {'available': False}
        else:
            results[package] = {'available': True, 'oldversion': packageinfo.group(1), 'newversion':packageinfo.group(2)}
            # Remove checked packages from count
            updatecount -= 1
    results['system'] = {'available': bool(updatecount), 'count': updatecount, 'all': all_updates}

    return results

	
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check for updates available via apt')
    parser.add_argument('package', nargs='*',
                    help='A package to check for updates')

    args = parser.parse_args()

    print(json.dumps(check_updates(args.package)))