#/bin/bash

fn1=/backup/$(date +"%Y_%m_%d")_wlanthermo_backup.tgz

printf 'Create Backup:\n '$fn1'\n'

if [ ! -d /backup ]; then
    mkdir /backup
fi

tar czf $fn1 /var/www/conf /var/www/thermolog /var/www/thermoplot

ls -lah /backup


