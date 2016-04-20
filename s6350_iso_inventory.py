#!/usr/bin/env python

#
# The s6350_iso_inventory program does a full multi-tag inventory
# of all tags in the RFID reader field.  It uses the ISO inventory
# command with 16 time slots.  The following data from each tag
# found can be returned.
#
# Transponder ID
# The Data Storage Format Identifier (DSFID)
#
# See TI 6350 user manual and the ISO 15693-3 document for more information.
#

import io
import sys
import serial


#
# The getReturnPacket function reads a reply packet from the S6350 reader.
# It does some checking of the data and if the packet is intact and the
# checksum is right it will return the packet to the calling program as a
# list of integers.
#
# The get return packet also checks for functional and communication errors.
# A functional error occurs if the RFID reader doesn't work.  This is
# indicated if no data is read from the RFID reader and the serial connection
# times out.  Communication errors are those where the reader works, but the
# returned data is corrupt as indicated by the checksum bytes.  Both of these
# errors are fatal, so if they occur a message will be printed and the program
# will exit.
#
# There could also be ISO command errors.  Those are not necessarily fatal
# and are handled in the chkErrorISO routine.
#

def getReturnPacket(tiser):

    #
    # We read the returned data from the reader in 2 passes.  First we read
    # the first two bytes.  The second byte is the length of the entire returned
    # packet.  From that we determine how many more bytes to read which are then
    # read in the second pass.
    #

    line_size = tiser.read(2)  # first pass, read first two bytes of reply

    if len(line_size) < 2:
        print ("No data returned.  Is the reader turned on?")
        tiser.close()
        sys.exit()

# second pass
#    print ("Reply length is " + str(ord(line_size[1])) + " bytes.")
    # get the rest of the reply
    line_data = tiser.read((ord(line_size[1]) - 2))
#    print ("I read " + str(len(line_data)) + " bytes.")

#
# The returned data is in the form of string objects.  Use that data to form
# a single response list of integers.  Integers are exactly what the RFID reader
# is sending back.  Doing this makes it easier to process the returned data.
#

    rddat_len = ord(line_size[1])  # this is the length of the entire response
    rddat = []
    idx = 0

    rddat.append(ord(line_size[0]))  # response SOF
    rddat.append(ord(line_size[1]))  # response size
# In the next line the -2 accounts for the SOF and size bytes done above.
    while idx < (rddat_len - 2):  # do the rest of the response
        rddat.append(ord(line_data[idx]))
        idx += 1

#
# Compute the checksum.  To compute the checksum of the returned data you just
# take the XOR of all the data bytes that were returned and compare with the checksum
# bytes that were returned.
#
# The 'while' statment ranges from 0 to the length of the returned data - 2.  The
# minus 2 is to adjust for the index (we number from 0) and also so that we do not
# include the returned last checksum bytes in our own calculation.  We compute the
# checksum on the returned data bytes, but not including the returned checksum bytes.
#

    chksum = 0
    idx = 0
    while idx < (rddat_len - 2):
        chksum ^= rddat[idx]
        idx += 1

#
# Compare the checksums and if they don't match then bail out.
# If they do match then all is well and all that remains is to
# dig out and print the tag data.
#

    if chksum != (rddat[rddat_len - 2]):  # and compare them
        print("Checksum error!")
#    print (chksum)
#    print (rddat[rddat_len - 2])
        tiser.close()
        sys.exit()

    return rddat  # return the reader data as a list


#
# The chkErrorISO function will take a packet returned by the
# reader as a list of bytes and check it for any operational
# errors.  Operational errors are ones where the reader is
# functional and communication is functional but something
# went wrong with the requested operation, for example asking
# for a tag UID that does not belong to any tag in the field.
#
# Note that functional errors and communication errors are
# checked for in the getReturnPacket routine.
#
# The routine will return a list that contains the ISO error
# code as an integer and the meaning of the error as a string.
# An error code of 0 means no error (OK or command success).
#

def chkErrorISO(rddat):

    if (len(rddat) == 10) and (rddat[5] == 0x10):  # if there is an error
        error_code = rddat[7]  # get the code from the reader
        error_meaning = {
            "0x1": "Transponder not found.",
            "0x2": "Command not supported.",
            "0x4": "Packet flags invalid for command.",
        }.get(hex(rddat[7]), "Unknown error code.")
    else:
        error_code = 0  # else 0 = all OK
        error_meaning = "OK"

    return [error_code, error_meaning]  # return code and meaning as a list


####################################
#
# Main body of the code starts here.
#
####################################

#
# Check that there is at least one argument which hopefully will be
# the serial port ID that is to be used.
#

if len(sys.argv) < 2:
    print ("Usage: " + sys.argv[0] + " serial_port_to_use")
    sys.exit()

#
# The TI reader defaults to 57600 baud, 8 bit data, 1 stop bit and no parity.
# There is no handshaking.
#
# Note that the timeout here is set to 5 seconds.  That is more than enough
# time to allow the TI RFID reader to turn on its radio, command a tag, and get
# data back from it.  We assume that if we time out and we don't have any data
# then the RFID reader is not on line.
#

try:
    tiser = serial.Serial(sys.argv[1], baudrate=57600, bytesize=8,
                          parity='N', stopbits=1, timeout=5, xonxoff=0, rtscts=0, dsrdtr=0)
except:
    print ("Usage: " + sys.argv[0] + " serial_port_to_use")
    print ("Can't open " + sys.argv[1] + ".")
    print ("Under linux or Apple OS you need the full path, ie /dev/ttyUSB0.")
    print ("Under windows use the communication port name, ie COM8")
    sys.exit()

# Construct a simple python list to use as a stack to store inventory
# masks in the event of a collision.  Python is great for this.  In
# this application all mask values are handled as collections of bytes.

maskStack = []

#
# To use the write() method in python it needs to be in the form of a
# string or a buffer, which is just a pointer into memory.  This code
# forms an array of bytes from a list that contains the command to send
# and then uses a buffer (memoryview) to write it out.
#
# Note that the S6350 reader uses a wrapper that encapsulates all
# ISO commands.  Every ISO commands needs to have this wrapper with
# the S6350 reader.  For some commands the entire length is not
# known ahead of time, so some pieces are filled in later and the
# checksum bytes generated last and filled in.  This command is a
# good example of a command where the length can change, in this
# case as the mask grows in length.
#
# In this wrapper, the bytes are as follows:
#
# 0: SOF
# 1 & 2: length LSB and MSB respectively, filled in later
# 3 & 4: TI reader address fields, alsways set to 0
# 5: TI reader command flags
# 6: TI reader ISO pass thru command, always 0x60
#

read_transponder_details = [0x01, 0, 0, 0, 0, 0, 0x60]  # the ISO wrapper

#
# Extend the list with the actual ISO command without the SOF, CRC16 and EOF
# On the first inventory pass, the mask length is zero.  It will grow as
# collisions are encountered, but for now form the ISO inventory command
# asking for 16 time slots, and no mask.
#
# The bytes that extend the list are as follows:
#
# 7: ISO reader config byte 0.The value in this case is 0x11
# 8: Tag flags.  In this case indicating 16 time slots (0x07)
# 9: The ISO command.  In this case 0x01
# 10: The mask length in BITS for doing the inventory.  In this case it is 0
#

read_transponder_details.extend([0x11, 0x07, 0x01, 0])

#
# Extend the list 1 more time with places for the checksum bytes.
# Those will be computed and added later to the resulting byte array
# that is formed to send to the reader.
#

read_transponder_details.extend([0, 0])  # the two checksum bytes

#
# Now that the list containing the initial command template is done, it
# is possible to compute the length of the command and create the byte
# array.
#

command_len = len(read_transponder_details)
command = bytearray(command_len)
idx = 0

for i in read_transponder_details:
    command[idx] = i
    idx += 1

# Fill in the length

command[1] = command_len

# Compute and fill in the two checksum bytes

chksum = 0
idx = 0
while idx < (command_len - 2):
    chksum ^= command[idx]
    idx += 1

command[command_len - 2] = chksum  # 1st byte is the checksum
# 2nd byte is ones comp of the checksum
command[command_len - 1] = chksum ^ 0xff

# Send out the command to the reader and get the reply

x_str = raw_input("Enter any string to get ISO transponder details: ")
tiser.write(memoryview(command))  # memoryview is the same as buffer
response = getReturnPacket(tiser)  # read the response from the reader


#
# Check if any ISO errors have occurred.
#

iso_errors = chkErrorISO(response)
if iso_errors[0] != 0:
    # for grins, print the error code
    print ("Error code is: " + hex(iso_errors[0]))
    print iso_errors[1]  # and the meaning
    print


# Now enter into a processing loop where we look for tags to identify
# themselves.  There are three subloops that take place here.
#
# The first loop is to process valid data timeslot flags.  If there
# is a tag in a time slot and no collision, then the tag ID and
# the Data Storage Format Identifier (DSFI) will be shown.
#
# The second loop is to process the collision timeslot flags.
# If there is a collision, then the time slot number is combined with
# the mask to create a new mask, and it is pushed onto the mask stack.
#
# The third loop is to process any masks that have been pushed onto
# the mask stack.  If the mask stack is not empty, the stack is
# popped and the data is used to form a new inventory commend.  The
# command is sent to the reader and these three loops are run again.
# The inventory is complete when we reach the end of this loop and
# the stack is empty.
#

tagCount = 0
moreToDo = True


# while there is data to do and no errors
while moreToDo and (iso_errors[0] == 0):

    #
    # Check the Valid Data Flags first.  If no flags are set, then it means that no
    # RFID tag was seen in the field.  Set flags mean that tags successfully
    # identified themselves, and the data can be dug out of the returned data field.
    # Tag data is an 80 bit (10 byte) field.
    #
    # There is never supposed to be a Valid Data Flag and a Collision Flag set for
    # the same time slot, so Collisions can be handled after we deal with the
    # Valid Data Flags.
    #

    if response[7] != 0 or response[8] != 0:  # we have data

        numTags = 0  # number of tags found on this loop
        z = 0

        while z < 8:  # compute how much data there is
            if (response[7] & (0x01 << z)) != 0:
                numTags += 1
            if (response[8] & (0x01 << z)) != 0:
                numTags += 1
            z += 1

        z = 0
        while z < numTags:  # dig out tag data
            tagCount += 1
            print("Transponder " + str(tagCount))
            idx = z * 10  # each collection of tag data takes 10 bytes
            print("ID: " + "0x%0.2x" % response[idx + 20] + "%0.2x" % response[idx + 19]
                  + "%0.2x" % response[idx + 18] + "%0.2x" % response[idx + 17]
                  + "%0.2x" % response[idx + 16] + "%0.2x" % response[idx + 15]
                  + "%0.2x" % response[idx + 14] + "%0.2x" % response[idx + 13])

            print("DSFID: " + "0x%0.2x" % response[idx + 12])
            print
            z += 1


#
# Next process the collisions.  When a collision is found, combine the
# time slot where the collision took place with the inventory mask to
# form a new mask.  Push the mask byte by byte onto the stack with a
# bit count at the end.  Data from the stack will be used every time
# the loop iterates.
#

    if response[9] != 0 or response[10] != 0:  # we have collisions

        #
        # Do the collision flags.  Here's how it works:
        #
        # If a flag is set:
        #
        # 1. Compute the number of BYTES in the existing mask.
        #
        # 2. Push all bytes except the MSByte onto the stack.
        #
        # 3. If the MSByte is NOT a padded nibble, push it onto the stack too.
        #
        # 4. If the MSByte is a padded nibble, put the time slot value
        # into the 4 MSbits and push it onto the stack.
        #
        # 5. If the MSByte was not a padded nibble, then use the time slot
        # value to form a new paddded nibble & push it onto the stack.
        #
        # 6. Push one more byte onto the stack containing the number of
        # BITS in the mask.  This will be used to form the next inventory
        # command, and indicate how many times the stack needs to be popped
        # to get off the entire new mask.
        #
        # Note that the number of bits in the mask will increase in units
        # of 4 bits.  That's the length of the time slot counter.
        #
        # Both the least significant and most significant collision
        # flags can be processed at the same time.  Just add 8 to the
        # time slot value for the most significant flags.
        #

        numMaskBytes = 0
        z = 0
        while z < 8:

            # Do the Least Significant collision bits

            if (response[9] & (0x01 << z)) != 0:
                numMaskBytes = command[10] / 8  # compute BYTES
                idx = 0
                while idx < numMaskBytes:  # push existing mask bytes onto the stack
                    maskStack.extend([command[11 + idx]])
                    idx += 1


# Adjust MSB with the time slot value

                if (command[10] % 8) != 0:  # if a MS nibble exists
                    timeSlot = z << 4  # compute and position time slot value
                    timeSlot |= command[11 + idx]
                    maskStack.extend([timeSlot])  # push MS bits onto the stack

                else:  # no existing MS nibble
                    timeSlot = z  # get time slot value
                    maskStack.extend([timeSlot])  # push MS bits onto the stack

                # push number of bits onto stack
                maskStack.extend([command[10] + 4])

#
# Now do the Most Significant collision bits.
# It's the same as the Least Significant bits but just add 8 to the timeSlot values.
#

            if (response[10] & (0x01 << z)) != 0:
                numMaskBytes = command[10] / 8  # compute BYTES
                idx = 0
                while idx < numMaskBytes:  # push existing mask bytes onto the stack
                    maskStack.extend([command[11 + idx]])
                    idx += 1

# Adjust MSB with the time slot value

                if (command[10] % 8) != 0:  # if a MS nibble exists
                    # compute and position time slot value
                    timeSlot = (z + 8) << 4
                    timeSlot |= command[11 + idx]
                    maskStack.extend([timeSlot])  # push MS bits onto the stack

                else:  # no existing MS nibble
                    timeSlot = z + 8  # get time slot value
                    maskStack.extend([timeSlot])  # push MS bits onto the stack

                # push number of bits onto stack
                maskStack.extend([command[10] + 4])

            z += 1  # increment to next time slot bit

#
# Last is to process the mask stack.
# If the stack is not empty, then set up and start the next
# inventory iteration.  If the stack is empty, or if an error
# has occurred, then we are done.  See comments above for what
# is in the ISO command wrapper.
#

    if len(maskStack) != 0:  # if the mask stack is not empty

        moreToDo = True
        read_transponder_details = [
            0x01, 0, 0, 0, 0, 0, 0x60]  # the ISO wrapper

#
# 7: ISO reader config byte 0.The value in this case is 0x11
# 8: Tag flags.  In this case indicating 16 time slots (0x07)
# 9: The ISO command.  In this case 0x01
# 10: The mask length in BITS for doing the inventory
#

        numMaskBits = maskStack.pop()  # Mask length in bits
        read_transponder_details.extend([0x11, 0x07, 0x01, numMaskBits])

#
# At this point, we should check to see that the mask is not 64 bits
# in length. Such a condition can only occur if there are two identical
# tags in the field, or some other very strange fault.
#

        if numMaskBits == 64:
            print ("Identical (cloned) tags or operational fault!")
            tiser.close()
            sys.quit()  # bail out

# Continue

        numMaskBytes = numMaskBits / 8  # compute number of mask bytes to pop
        if (numMaskBits % 8) != 0:  # adjust if a MS nibble exists
            numMaskBytes += 1

#
# Next form the mask. It goes into the command LSBs first,
# but the MSBs are popped off the stack first.  As we know
# how many bytes there should be, we just adjust how they
# are put into the command to account for this.  Fortunately
# python's pop method makes this very easy by using a negative
# index.
#

        idx = numMaskBytes * -1  # form a negative index
        while idx < 0:
            read_transponder_details.extend(
                [maskStack.pop(idx)])  # mask, LSBs first
            idx += 1

#
# Now account for the checksums
#

        read_transponder_details.extend([0, 0])  # the two checksum bytes

#
# Now that the list containing the initial command template is done, it
# is possible to compute the length of the command and create the byte
# array.
#

        command_len = len(read_transponder_details)
        command = bytearray(command_len)
        idx = 0

        for i in read_transponder_details:
            command[idx] = i
            idx += 1

# Fill in the length

        command[1] = command_len

# Compute and fill in the two checksum bytes

        chksum = 0
        idx = 0
        while idx < (command_len - 2):
            chksum ^= command[idx]
            idx += 1

        command[command_len - 2] = chksum  # 1st byte is the checksum
        # 2nd byte is ones comp of the checksum
        command[command_len - 1] = chksum ^ 0xff

# Send out the command to the reader and read the response

        tiser.write(memoryview(command))  # memoryview is the same as buffer
        response = getReturnPacket(tiser)  # read the response from the reader

#
# Check if any ISO errors have occurred.
#

        iso_errors = chkErrorISO(response)
        if iso_errors[0] != 0:
            # for grins, print the error code
            print ("Error code is: " + hex(iso_errors[0]))
            print iso_errors[1]  # and the meaning
            print

    else:  # else if the mask stack is empty
        moreToDo = False


if tagCount == 0:
    print ("No RFID tags found.")

else:
    print ("Total tags found: " + str(tagCount))

tiser.close()
