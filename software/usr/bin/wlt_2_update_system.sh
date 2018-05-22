#!/bin/bash
# Fix broken or aborted installations first
touch /var/www/tmp/update
if [ $# > 1 ]
then
    if [[ "$1" = "--full" ]]
    then
        full_upgrade=1
    fi
fi

echo "Fixing broken installations..." > /var/www/tmp/update.log
apt -y install --fix-broken &>> /var/www/tmp/update.log
echo "Updating package list..." >> /var/www/tmp/update.log
apt update &>> /var/www/tmp/update.log

if [[ -z "$full_upgrade" ]]
then
    echo "Hold back wlanthermo..." >> /var/www/tmp/update.log
    apt-mark hold wlanthermo &>> /var/www/tmp/update.log
fi

# Do full upgrade
apt -y dist-upgrade &>> /var/www/tmp/update.log

if [[ -z "$full_upgrade" ]]
then
    echo "Unhold wlanthermo..." >> /var/www/tmp/update.log
    apt-mark unhold wlanthermo &>> /var/www/tmp/update.log
fi

# Cleanup afterwards
echo "Cleaning up..." >> /var/www/tmp/update.log
apt -y autoremove &>> /var/www/tmp/update.log
apt -y clean &>> /var/www/tmp/update.log

# Update available updates
/etc/cron.daily/wlanthermo_updatecheck

# Move log (and clear GUI)
now=$(date +%Y%M%d)
mv /var/www/tmp/update.log /var/log/WLAN_Thermo/update-$now.log
ln -srf /var/log/WLAN_Thermo/update-$now.log /var/log/WLAN_Thermo/update.log 
rm /var/www/tmp/update