#!/usr/bin/python3
# coding=utf-8

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

import bz2
import logging
import os
import shutil
import sys
import tempfile

from wlanthermo.display import Display

PORT = '/dev/serial0'
BAUDCOMM = 9600
# Die nextion-Bibliothek unterstützt höchstens 230400 Baud (früher: 460800)
BAUDUPLOAD = 230400


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        sys.exit('usage: python3 %s directory [variant]' % sys.argv[0])

    file_path = sys.argv[1]
    variant_suffix = '_' + sys.argv[2] if len(sys.argv) > 2 else ''

    if not os.path.exists(file_path):
        sys.exit('directory "{}" not found'.format(file_path))

    # Der Fortschritt der Bibliothek ("Uploaded: x%") geht auf stdout (-> Update-Log)
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout, format='%(message)s')
    logging.getLogger('nextion').setLevel(logging.INFO)

    display = Display()
    print('Connecting...')
    # Die Bibliothek probiert alle Baudraten durch, beginnend mit BAUDCOMM
    if not display.start(PORT, BAUDCOMM):
        sys.exit('No connection!')

    try:
        info = display.device_info
        print('Connected!')
        print('Model: ' + info['model'])
        print('Firmware: ' + info['firmware'])
        print('Serial: ' + info['serial'])
        print('Flash size: ' + info['flash_size'])

        file_name = '{file_path}{model}{variant}.tft'.format(
            file_path=file_path, model=info['model'].split('_')[0], variant=variant_suffix)
        print('Now flashing {file}'.format(file=file_name))

        if os.path.isfile(file_name + '.bz2'):
            file_name += '.bz2'
            opener = bz2.BZ2File
        elif os.path.isfile(file_name):
            opener = open
        else:
            sys.exit('file {} not found'.format(file_name))

        # Die Bibliothek braucht eine echte Datei (Größe über den Dateideskriptor),
        # deshalb wird eine .bz2-Datei vorher entpackt.
        with opener(file_name, 'rb') as src, tempfile.TemporaryFile(dir='/var/tmp') as tft:
            shutil.copyfileobj(src, tft)
            tft.flush()
            fsize = tft.tell()
            tft.seek(0)
            print('uploading %s (%i bytes)...' % (file_name, fsize))
            try:
                too_big = fsize > int(info['flash_size'])
            except ValueError:
                too_big = False
            if too_big:
                sys.exit('File too big!')
            try:
                display.upload_firmware(tft, BAUDUPLOAD)
            except Exception as e:
                sys.exit('Upload failed: {}'.format(e))
    finally:
        display.stop()

    print('File uploaded to Display!')


if __name__ == '__main__':
    main()
