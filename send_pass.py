#!/usr/bin/env python

import time
import serial
from datetime import datetime
ser = serial.Serial(
    port='/dev/ttyUSB1',
    baudrate=115200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
)
epoch = datetime.utcfromtimestamp(0)
def get_time():
    now = datetime.utcnow() - epoch
    return now.total_seconds()


input = 1
# initialize wasa board
ser.write("ATQ1\rATE0\rAT S120=3\r")

# states
transistor_on = "ATS130=1\r"
transistor_off = "AT S130=0\r"

password = "F"
start_password=password
sync_pattern_start = "001000001"
sync_pattern_end = "00001111"
symbol_time = 1  # 1 sec
thres_time = symbol_time/10
# send the bit array to serial and sleep for a symbol time afterwards
def send_bitarray(bitarray):
    for digit in bitarray:
        while abs((get_time()-start) % symbol_time) > (thres_time):
            1+1 #time.sleep(thres_time/10)
        print "bit: " + digit + " time: " + str((get_time()-start)/symbol_time)
        if digit == '0':
            ser.write(transistor_on)
        else:
            ser.write(transistor_off)
        ##time.sleep(symbol_time

# clean up from possible previous transistor states
ser.write(transistor_off)

# sync pattern start
start = get_time()
send_bitarray(sync_pattern_start)

# send password
while password != "":
    letter = password[:1]
    password = password[1:]
    binary = bin(ord(letter))[2:]
    binary = binary.zfill(8)

    send_bitarray(binary)

# sync pattern end
send_bitarray(sync_pattern_end)
print bin(ord(start_password))
ser.write(transistor_off)
