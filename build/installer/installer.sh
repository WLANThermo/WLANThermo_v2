#!/bin/bash

echo "Starting WLANThermo installation"
echo "----------------------------------------------------------"

if [ `whoami` != root ]; then
    echo "Please run this script as root or using sudo!"
    exit
fi
  
grep 'VERSION_ID="9"' /etc/os-release &> /dev/null
if [ $? -ne 0 ]; then
  echo "This installer need Raspbian Stretch!"
  exit
fi

if [ "$1" == "--image-mode" ]; then
  IMAGE_MODE=TRUE
else
  IMAGE_MODE=FALSE
fi

#
# Stop processes to speed up installation
#
if [ "$IMAGE_MODE" == "FALSE" ]; then
  echo "Stopping WLANThermo processes"
  echo "----------------------------------------------------------"
  systemctl stop WLANThermo.service
  systemctl stop pigpiod.service
  if [ -f /var/run/wlt_2_nextion.pid ]; then
    kill $(cat /var/run/wlt_2_nextion.pid)
  fi
  pkill gnuplot
fi

lines=`grep --max-count 1 --line-regexp --line-number --text '# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----' $0 | cut -d: -f 1`
startline=$((lines + 1))

if command -v systemctl > /dev/null && systemctl | grep -q '\-\.mount'; then
  SYSTEMD=1
elif [ -f /etc/init.d/cron ] && [ ! -h /etc/init.d/cron ]; then
  SYSTEMD=0
else
  echo "Unrecognised init system"
  return 1
fi

program=wlanthermo

echo "Updating System:"
echo "----------------------------------------------------------"
apt update
apt -y dist-upgrade
apt -y autoremove

echo "Extract the package"
echo "----------------------------------------------------------"
tail -n +$startline $0 > /tmp/${program}.deb
ls -l /tmp/${program}.deb

echo "Install depencies:"
echo "----------------------------------------------------------"
apt -y install $(dpkg -I /tmp/${program}.deb | grep 'Depends:' | sed -e 's/,//g' -e 's/ *Depends: *//')

echo "Install /tmp/${program}.deb"

dpkg -i /tmp/${program}.deb
echo "----------------------------------------------------------"

url=$(cat /etc/hostname)
echo " "
echo "===================================================================================================="
echo "========*********************************************************************************==========="
echo "========***********    WLANThermo installed completely! Please reboot now!    ***********==========="
echo "========***********         Open http://$url in a browser afterwards!         ***********==========="
echo "========*********************************************************************************==========="
echo "===================================================================================================="
echo " "

exit 0
# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----
