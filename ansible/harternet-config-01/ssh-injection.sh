#!/usr/bin/env bash
# Initial ssh key injection can't be done by Ansible since it relies on ssh
# access through a key.  So this script does initial injection
# Note: requires ssh client and sshpass utility to be installed

# check for expected command line argument or give usage
if [ -z "$1" ]
then
   echo "usage: ssh-injection hostname"
   exit
fi

# set script variables
hostname=$1
username=cloudstack
password=cloudstack
keyname=cloudstack.key
email="admin@harter.priv"
management_ip="192.168.0.9"
sshaddr="$username@$hostname"
sshargs="-o StrictHostKeyChecking=no -o PubkeyAuthentication=no -o PreferredAuthentications=password"

# generate the cloudstack management key that will be used if none exists
if [ ! -f "$keyname" ]
then
    ssh-keygen -a 100 -t ed25519 -f "$keyname" -C "$email" -q -N ""
fi

# temporarily setup ssh access using key identity to cloudstack account
echo "Temporarily setting up  public key access to throw away user account..."
echo "--------------------"
sshpass -p $password ssh-copy-id $sshargs -i $keyname $sshaddr
echo ""
echo ""

# now that we can use ssh key access to the user with root privileges, copy that key to the root user
# change ssh arguments to using ssh key identity
sshargs="-o IdentitiesOnly=yes"
echo "Injecting public key access into root account..."
echo "--------------------"
ssh $sshargs -i $keyname $sshaddr "echo $password | sudo -S cp ~/.ssh/authorized_keys /root/.ssh/authorized_keys"
echo ""
echo ""

# the following could maybe now be done from ansible since we now have ssh key access

# we have now successfully injected cloudstack management key into root
# start using root public key access to tighten security
sshaddr="root@$hostname"

# secure ssh access, only allow access from this management server using the management key
# order is important here, if you deny all first, won't be able to reconnect
echo "Only allow access from the ansible management host ip..."
echo "--------------------"
ssh $sshargs -i $keyname $sshaddr "echo sshd: $management_ip >> /etc/hosts.allow"
ssh $sshargs -i $keyname $sshaddr "echo sshd: ALL >> /etc/hosts.deny"
echo ""
echo ""

# change sshd daemon to only allow public key login
echo "Only allow sshd logins using the authorized ansible management public key..."
echo "--------------------"
ssh $sshargs -i $keyname $sshaddr 'sed -i "s/#PubkeyAuthentication yes/PubkeyAuthentication yes/g" /etc/ssh/sshd_config'
ssh $sshargs -i $keyname $sshaddr 'sed -i "s/#PasswordAuthentication yes/PasswordAuthentication no/g" /etc/ssh/sshd_config'
ssh $sshargs -i $keyname $sshaddr 'systemctl restart sshd'
echo ""
echo ""

# disable / delete original user
echo "Throw away the temporary account after we finish ansible management access setup..."
echo "--------------------"
#ssh $sshargs -i $keyname $sshaddr "deluser --remove-all-files $username"
#ssh $sshargs -i $keyname $sshaddr "delgroup $username"
echo ""
echo ""
