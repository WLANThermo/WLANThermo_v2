#!/usr/bin/python
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

import threading
import time
import os
import sys
import serial


PORT = '/dev/ttyAMA0'
BAUDCOMM = 9600
BAUDUPLOAD = 115200
CHECK_MODEL = 'NX3224T028'

if len(sys.argv) != 2:
	print 'usage: python %s file_to_upload.tft' % sys.argv[0]
	exit(-2)

file_path = sys.argv[1]

if os.path.isfile(file_path):
	print 'uploading %s (%i bytes)...' % (file_path, os.path.getsize(file_path))
else:
	print 'file not found'
	exit(-1)

fsize = os.path.getsize(file_path)
print('Filesize: ' + str(fsize))

ser = serial.Serial(PORT, BAUDCOMM, timeout=.1, )

acked = threading.Event()
stop_thread = threading.Event()

def reader():
    global acked
    global ser
    while stop_thread.is_set() == False:
        r = ser.read(1)
        if r == '':
            continue
        elif '\x05' in r:
            acked.set()
            continue
        else:
            print '<%r>' % r
            continue

            
def upload():
    global acked
    global ser
    global stop_thread
    ser.write('tjchmi-wri %i,%i,0' % (fsize, BAUDUPLOAD))
    ser.write("\xff\xff\xff")
    ser.flush()
    acked.clear()
    ser.baudrate = BAUDUPLOAD
    ser.timeout = 0.1
    threader.start()
    print 'Waiting for ACK...'
    acked.wait()
    print 'Uploading...'
    with open(file_path, 'rb') as hmif:
        dcount = 0
        while True:
            #time.sleep(.1)
            data = hmif.read(4096)
            if len(data) == 0: break
            dcount += len(data)
            #print 'writing %i...' % len(data)
            ser.write(data)
            acked.clear()
            sys.stdout.write('\rDownloading, %3.1f%%...' % (dcount/ float(fsize)*100.0))
            sys.stdout.flush()
            #print 'waiting for hmi...'
            acked.wait()
        print('')
    stop_thread.set()
    threader.join(1)


threader = threading.Thread(target = reader)
threader.daemon = True

no_connect = True
for baudrate in (2400, 4800, 9600, 19200, 38400, 57600, 115200):
    ser.baudrate = baudrate
    ser.timeout = 3000/baudrate + 0.2
    print('Trying with ' + str(baudrate) + '...')
    ser.write("\xff\xff\xff")
    ser.write('connect')
    ser.write("\xff\xff\xff")
    r = ser.read(128)
    if 'comok' in r:
        print('Connected with ' + str(baudrate) + '!')
        no_connect = False
        status, unknown1, model, unknown2, version, serial, flash_size = r.strip("\xff\x00").split(',')
        print('Status: ' + status)
        print('Model: ' + model)
        print('Version: ' + version)
        print('Serial: ' + serial)
        print('Flash size: ' + flash_size)
        if fsize > flash_size:
            print('File too big!')
            break
        if not CHECK_MODEL in model:
            print('Wrong Display!')
            break
        upload()
        break

if no_connect:
    print('No connection!')
else:
    print('File written to Display!')

ser.close()

