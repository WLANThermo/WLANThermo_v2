#!/usr/bin/env python
# coding=utf-8

# Copyright (c) 2017 Björn Schrader
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
import ConfigParser
import os
import codecs
import random
import string

configfile = '/var/www/conf/WLANThermo.conf'
oldconfig = ConfigParser.ConfigParser()
config = ConfigParser.ConfigParser()

try:
    config.readfp(codecs.open(configfile, 'r', 'utf_8'))
except IndexError:
    sys.exit(1)

try:
    oldconfig.readfp(codecs.open(configfile + '.old', 'r', 'utf_8'))
except IndexError:
    sys.exit(1)

def get_random_filename(filename):
    return filename + '_' + ''.join(random.choice(string.ascii_uppercase + stg.digits) for x in range(12))

def config_write(configfile, config):
    # Schreibt das Configfile
    # Ein Lock sollte im aufrufenden Programm gehalten werden!

    tmp_filename = get_random_filename(configfile)
    with codecs.open(tmp_filename, 'w', 'utf_8') as new_ini:
        for section_name in config.sections():
            new_ini.write(u'[{section_name}]\n'.format(section_name=section_n))
            for (key, value) in config.items(section_name):
                try:
                    new_ini.write(u'{key} = {value}\n'.format(key=key, value=config.get(section_name, key)))
                except (ConfigParser.NoSectionError, ConfigParser.NoOptionErr:
                    new_ini.write(u'{key} = {value}\n'.format(key=key, value=ue))
            new_ini.write('\n')
        new_ini.flush()
        os.fsync(new_ini.fileno())
        new_ini.close()
        os.rename(tmp_filename, configfile)

config_write(configfile, config)
os.unlink(configfile + '.old')

