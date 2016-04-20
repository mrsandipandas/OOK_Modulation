#!/usr/bin/env python

#
# This demos getting the version information from a TI S6350 RFID reader.
#
#

import io
import sys
import serial

#
# Check that there is at least one argument which hopefully will be
# the serial port ID that is to be used.
#

if len(sys.argv) < 2:
    print ("Usage: " + sys.argv[0] + " serial_port_to_use")
    sys.exit()


#
# The TI reader defaults to 57600 baud, 8 bit data, 1 stop bit and no parity.
# There is also no handshaking.
#

try:
    tiser = serial.Serial(sys.argv[1], baudrate=57600, bytesize=8,
                          parity='N', stopbits=1, timeout=0.5, xonxoff=0, rtscts=0, dsrdtr=0)
except:
    print ("Usage: " + sys.argv[0] + " serial_port_to_use")
    print ("Can't open " + sys.argv[1] + ".")
    print ("Under linux or Apple OS you need the full path, ie /dev/ttyUSB0.")
    print ("Under windows use the communication port name, ie COM8")
    sys.exit()

#
# Form a carrier on/off command template.  We fill in the argument for ON or
# OFF and the checksum bytes later.  To use the write() method in python it
# needs to be to be in the form of a string or a buffer, which is just a
# pointer into memory.  This code forms an array of bytes from a list that
# contains the command to send and then uses a buffer (memoryview) to write
# it out.
#

carrier_onoff_command = [0x01, 0x0a, 0, 0, 0, 0, 0xf4, 0, 0, 0]

command = bytearray(10)
idx = 0

for i in carrier_onoff_command:
    command[idx] = i
    idx += 1


# Get the argument to turn the carrier ON or OFF from the user.

arg = " "  # init this to be some string

while (arg != 'on') and (arg != 'ON') and (arg != 'off') and (arg != 'OFF'):

    arg = raw_input("Turn carrier ON or OFF? : ")

#
# Update the command with the entered argument to turn the carrier ON
# of OFF.  Note that the command template already is set to turn the
# carrier OFF, so we only need to do something here if the user wants
# to turn the carrier ON.
#

if (arg == 'on') or (arg == 'ON'):

    command[7] = 0xff


# Compute and fill in the two checksum bytes.

command_len = len(carrier_onoff_command)
chksum = 0
idx = 0
while idx < (command_len - 2):
    chksum ^= command[idx]
    idx += 1

command[command_len - 2] = chksum  # 1st byte is the checksum
command[command_len - 1] = chksum ^ 0xff  # 2nd byte is ones comp of checksum

tiser.write(memoryview(command))  # memoryview == buffer

#
# We read the returned data from the reader in 2 passes.  First we read
# the first two bytes.  The second byte is the length of the entire returned
# packet.  From that we determine how many more bytes to read which are then
# read in the second pass.
#
# Remember that in python the read() method returns data as string objects.
# So lots of conversions will be done to get integers or hex strings.
#

line_size = tiser.read(2)  # first pass, read first two bytes of reply

if len(line_size) < 2:
    print ("No data returned.  Is the reader turned on?")
    sys.exit()

# second pass
#    print ("Reply length is " + str(ord(line_size[1])) + " bytes.")
line_data = tiser.read((ord(line_size[1]) - 2))  # get the rest of the reply
#    print ("I read " + str(len(line_data)) + " bytes.")

#
#  The returned data is in the form of string objects.  Use that data to form
# a single response list of integers.  Integers are exactly what the RFID reader
# is sending back.  Doing this makes it easier to process the returned data.
#

response_len = ord(line_size[1])  # this is the length of the entire response
response = []
idx = 0

response.append(ord(line_size[0]))  # response SOF
response.append(ord(line_size[1]))  # response size
# In the next line the -2 accounts for the SOF and size bytes done above.
while idx < (response_len - 2):  # do the rest of the response
    response.append(ord(line_data[idx]))
    idx += 1

#
# Compute the checksum.  To compute the checksum of the returned data you
# just take the XOR of all the data bytes that were returned and compare with
# the checksum bytes that were returned.  The 'while' statment ranges from 0
# to the length of the returned data - 2.  The minus 2 is to adjust for the
# index (we number from 0) and also so that we do not include the returned
# last checksum bytes in our own calculation.  We compute the checksum on the
# returned data bytes, but not including the returned checksum bytes.

chksum = 0
idx = 0
while idx < (response_len - 2):
    chksum ^= response[idx]
    idx += 1

#
# Compare the checksums and if they match test that the data field
# has been set to zero.  A zero indicates command success.  Anything
# else is some kind of error.  The error code is reported in the code
# below.  See appendix B of the reader reference guide to determine what
# it means.
#

if chksum == (response[response_len - 2]):  # and compare them

    if response[7] == 0:
        print("Carrier successfully turned " + arg + ".")
    else:
        print("Command execution error, returned code is " + response[7] + ".")
        print("Carrier state not changed.")

else:
    print("Checksum error!")
#    print (chksum)
#    print (response[response_len - 2])

tiser.close()
