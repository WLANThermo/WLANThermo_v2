#/bin/bash

printf 'Lade Update herunter:'
wget -O /tmp/www.tgz  http://www.wlanthermo.com/dl/www.tgz

if [[ -s /tmp/www.tgz ]] ; then
  printf 'Entpacke Update nach /var/www/'
  tar xzf /tmp/www.tgz -C /var/www/
  printf '<p>Update fertig, bitte Browsercache leeren!</p>'
else
  printf '\n\n  Download fehlgeschlagen!\n\n'
fi


