#!/bin/bash

# get pass from user initially, this can be replaced as an argument to the script
read -s -p "Enter Password: " userpass

# lock screen with slock utility
slock &

# wait for 5 seconds
sleep 5

# unlock pc by simulating input with xdotool
xdotool type $userpass ; xdotool key Return;

