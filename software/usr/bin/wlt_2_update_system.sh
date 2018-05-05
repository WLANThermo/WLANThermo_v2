#!/bin/bash
# Fix broken or aborted installations first
if [ $# > 1 ]
then
    if [[ "$1" = "--full" ]]
    then
        full_upgrade=1
    fi
fi

echo "Fixing broken installations..." > /var/www/tmp/update
apt -y install --fix-broken &>> /var/www/tmp/update
echo "Updating package list..." >> /var/www/tmp/update
apt update &>> /var/www/tmp/update

if [[ -z "$full_upgrade" ]]
then
    echo "Hold back wlanthermo..." >> /var/www/tmp/update
    apt-mark hold wlanthermo &>> /var/www/tmp/update
fi

# Do full upgrade
apt -y dist-upgrade &>> /var/www/tmp/update

if [[ -z "$full_upgrade" ]]
then
    echo "Unhold wlanthermo..." >> /var/www/tmp/update
    apt-mark unhold wlanthermo &>> /var/www/tmp/update
fi

# Cleanup afterwards
echo "Cleaning up..." >> /var/www/tmp/update
apt -y autoremove &>> /var/www/tmp/update
apt -y clean &>> /var/www/tmp/update

# Update available updates
/etc/cron.daily/wlanthermo_updatecheck

# Move log (and clear GUI)
mv /var/www/tmp/update /var/log/WLAN_Thermo/update-$(date +%Y%M%d).log