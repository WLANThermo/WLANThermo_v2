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

if len(sys.argv) < 2 or len(sys.argv) > 3:
    sys.exit('usage: python %s directory [variant]' % sys.argv[0])

file_path = sys.argv[1]

if len(sys.argv) > 2:
    variant_suffix = '_' + sys.argv[2]
else:
    variant_suffix = ''

if not os.path.exists(file_path):
    sys.exit('directory "{}" not found'.format(file_path))

ser = serial.Serial(PORT, BAUDCOMM, timeout=.1, )

acked = threading.Event()
stop_thread = threading.Event()
threader = False

def reader():
    global acked
    global ser
    global threader
    
    while stop_thread.is_set() == False:
        r = ser.read(1)
        if r == '':
            continue
        elif '\x05' in r:
            acked.set()
            continue
        else:
            continue

def connect_old():
    ser.baudrate = BAUDCOMM
    ser.write('tjchmi-wri %i,%i,0' % (fsize, BAUDUPLOAD))
    ser.write("\xff\xff\xff")
    ser.flush()
    acked.clear()
    ser.baudrate = BAUDUPLOAD
    ser.timeout = 0.1
    print 'Waiting for ACK...'
    if acked.wait(1):
        return True
    else:
        return False

def connect_new():
    ser.baudrate = BAUDCOMM
    ser.write('whmi-wri %i,%i,0' % (fsize, BAUDUPLOAD))
    ser.write("\xff\xff\xff")
    ser.flush()
    acked.clear()
    ser.baudrate = BAUDUPLOAD
    ser.timeout = 0.1
    print 'Waiting for ACK...'
    if acked.wait(1):
        return True
    else:
        return False 
    
def upload(file_name):
    global acked
    global ser
    global stop_thread
    global threader
    
    threader = threading.Thread(target = reader)
    threader.daemon = True
    threader.start()
    
    print 'Connecting...'
    if not connect_new():
        print 'No ACK. Maybe old Firmware?, trying old command...'
        if not connect_old():
            stop_thread.set()
            threader.join(1)
            sys.exit('No ACK. Can´t establish connection!')
    print 'Uploading...'
    with open(file_name, 'rb') as hmif:
        dcount = 0
        while True:
            #time.sleep(.1)
            data = hmif.read(4096)
            if len(data) == 0: break
            dcount += len(data)
            #print 'writing %i...' % len(data)
            ser.write(data)
            acked.clear()
            if sys.stdout.isatty():
                sys.stdout.write('\rUploading, %3.1f%%...' % (dcount/ float(fsize)*100.0))
            else:
                print('Uploading, %3.1f%%...' % (dcount/ float(fsize)*100.0))
            sys.stdout.flush()
            #print 'waiting for hmi...'
            acked.wait()
        print('')
    stop_thread.set()
    threader.join(1)

no_connect = True
for BAUDCOMM in (9600, 115200, 2400, 4800, 19200, 38400, 57600):
    ser.baudrate = BAUDCOMM
    ser.timeout = 3000/BAUDCOMM + 0.2
    print('Trying with ' + str(BAUDCOMM) + '...')
    # Clear Buffers and Wake-Up
    ser.write("\xff\xff\xff")
    ser.write('sleep=0')
    ser.write("\xff\xff\xff")
    ser.flush()
    time.sleep(0.3)
    ser.flushInput()
    # Connect to Display
    ser.write('connect')
    ser.write("\xff\xff\xff")
    r = ser.read(128)
    if 'comok' in r:
        print('Connected with ' + str(BAUDCOMM) + '!')
        no_connect = False
        status, reserved, model, firmware, mcu_code, serial, flash_size = r.strip("\xff\x00").split(',')
        print('Status: ' + status)
        print('Model: ' + model)
        print('Firmware: ' + firmware)
        print('MCU code: ' + mcu_code)
        print('Serial: ' + serial)
        print('Flash size: ' + flash_size)
        
        file_name = '{file_path}{model}{variant}.tft'.format(file_path=file_path, model=model.split('_')[0], variant=variant_suffix)
        print 'Now flashing {file}'.format(file=file_name)
        if os.path.isfile(file_name):
            print 'uploading %s (%i bytes)...' % (file_name, os.path.getsize(file_name))
        else:
            sys.exit('file {} not found'.format(file_name))

        fsize = os.path.getsize(file_name)
        print('Filesize: ' + str(fsize))

        if fsize > flash_size:
            sys.exit('File too big!')

        upload(file_name)
        break

if no_connect:
    sys.exit('No connection!')
else:
    print('File uploaded to Display!')

