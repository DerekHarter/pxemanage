#!/usr/bin/env bash
# Generate all cloudstack paswords, ssh keys and secret encryption keys
# for a new cloudstack cluster.

keyname="keys/ansiblemanagement.key"
email="admin@harter.priv"
secretsfile="vars/secrets.yml"
pwcmd="pwgen -s -N 1 -n 42"
password_keys="
mysql_root_password
mysql_cloud_password
management_secret_key
database_secret_key"

# generate the cloudstack management key that will be used if none exists
if [ ! -f "$keyname" ]
then
    mkdir -p keys
    ssh-keygen -a 100 -t ed25519 -f "$keyname" -C "$email" -q -N ""
fi

# for safety make backup of current secrets just in case this is accidentally run
if [ -f "$secretsfile" ]
then
    cp --force --backup=numbered $secretsfile $secretsfile
fi

# iterate over all password keys, generating new random password and setting it
# in place in the secrets file
for password_key in $password_keys
do
    password=`$pwcmd`
    sed -i "s/${password_key}: .*/${password_key}: '${password}'/g" $secretsfile
done

