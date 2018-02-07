#!/usr/bin/env python3
# coding=utf-8

# Copyright (c) 2017, 2018 Björn Schrader
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import configparser
import os
import codecs
import random
import string
import argparse

def get_random_filename(filename):
    return filename + '_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))


def config_write(configfile, config, oldconfig):
    # Schreibt das Configfile
    # Ein Lock sollte im aufrufenden Programm gehalten werden!

    tmp_filename = get_random_filename(configfile)
    with codecs.open(tmp_filename, 'w', 'utf_8') as new_ini:
        for section_name in config.sections():
            new_ini.write(u'[{section_name}]\n'.format(section_name=section_name))
            for (key, value) in config.items(section_name):
                try:
                    new_ini.write(u'{key} = {value}\n'.format(key=key, value=oldconfig.get(section_name, key)))
                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    new_ini.write(u'{key} = {value}\n'.format(key=key, value=value))
            new_ini.write('\n')
        new_ini.flush()
        os.fsync(new_ini.fileno())
        new_ini.close()
        os.rename(tmp_filename, configfile)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Update current WLANThermo configuration from file')
    parser.add_argument('oldconfigfile',  metavar='filename', nargs='?',
                    help='A config file to merge into current configfile, deleted afterwards by default')
    parser.add_argument('-d', '--dontdelete', action='store_true',
                    help='Don´t delete file after merge')#
                    
    args = parser.parse_args()
    
    configfile = '/var/www/conf/WLANThermo.conf'
    oldconfigfile = args.oldconfigfile if args.oldconfigfile is not None else configfile + '.old'
    oldconfig = configparser.ConfigParser()
    config = configparser.ConfigParser()

    try:
        config.readfp(codecs.open(configfile, 'r', 'utf_8'))
    except (FileNotFoundError):
        print('Current config not found!', file=sys.stderr)
        sys.exit(1)

    try:
        oldconfig.readfp(codecs.open(oldconfigfile, 'r', 'utf_8'))
    except (FileNotFoundError):
        print('Old config not found!', file=sys.stderr)
        sys.exit(1)

    config_write(configfile, config, oldconfig)
    
    if not args.dontdelete:
        os.unlink(oldconfigfile)

