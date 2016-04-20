#Code for raspberry pi B+ with BCM GPIO configuration
from time import sleep
import time
import RPi.GPIO as GPIO
# use P1 header pin numbering convention
GPIO.setmode(GPIO.BCM)
GPIO.setup(14, GPIO.IN)
try:
  while True:
    count = 0
    cur_sec = int(round(time.time() * 1000))
    while cur_sec+5000 > int(round(time.time() * 1000)):
      if GPIO.input(14):
        count = count + 1
      sleep(.2)
    print count*12
except KeyboardInterrupt:
  GPIO.cleanup()
