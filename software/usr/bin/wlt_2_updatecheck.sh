#!/bin/bash
usage="$(basename "$0") [--help] [--full] -- program to check for WLANThermo updates

where:
    --help  show this help text
    --full  perform full check (with 'apt update')"

for var in "$@"
do
    if [[ "$var" = "--full" ]]
    then
        full_update=1
    elif [[ "$var" = "--help" ]]
        then
                echo $usage
                exit 0
        else
                echo "Unknown option: $var"
                exit 1
        fi
done

if [[ -n "$full_upgrade" ]]
then
    echo "Updating package list..."
    nice -n 15 apt update
fi

nice -n 15 /usr/bin/update_checker.py wlanthermo > /var/www/tmp/updates.json
