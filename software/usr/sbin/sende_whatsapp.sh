#!/bin/bash

#cd /opt/yowsup-master/src
#./yowsup-cli -c config.example -s $1 "$2"
/opt/yowsup/yowsup-cli demos --config /opt/yowsup/config --send $1 "$2"
