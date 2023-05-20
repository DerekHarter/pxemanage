#! /usr/bin/env python
"""This script is a command line tool that is used to register
new cloudstack hosts.  This script manages dhcpd and tftpd
resources to detect new dhcp requests, register the hosts
by adding them into the dhcp services, then set the hosts
up to perform a autoinstall network boot.

This script needs to modify root configuration files and
start and stop root services, so it needs to be run
as root user or with root sudo privileges currently.
"""
import os
import re
import signal
import subprocess
import time
from enum import Enum


# system globals
registration_done = False

# script global settings, may need to put these into config
# files later
registration_file = "/etc/dhcp/dhcpd.conf"
#registration_file = "./dhcpd.conf"
system_event_file = "/var/log/syslog"
#system_event_file = "./test-syslog"

subnet = "192.168.0.0"
netmask = "255.255.255.0"
router_ip = "192.168.0.1"
dns_servers = "192.168.0.1, 8.8.8.8, 8.8.4.4"
pxefilename = "pxelinux.0"

dhcp_conf_settings = \
"""
allow bootp;
allow booting;
max-lease-time 1200;
default-lease-time 900;
log-facility local7;

option ip-forwarding    false;
option mask-supplier    false;

"""
dhcpd_service_name = "isc-dhcp-server"
service_list = [dhcpd_service_name, "tftpd-hpa", "apache2"]

pxelinux_config_dir = "./files/tftp/pxelinux.cfg"
apache_server_ip = "192.168.0.9"
iso_image_name = "ubuntu22/ubuntu-22.04.2-live-server-amd64.iso"
tftpd_server_ip = "192.168.0.0"

ks_profile_dir = "./files/html/profiles"
ks_config_dir = "./files/html/ks"
ansible_manager_key = "../ansible/harternet-config-01/keys/ansiblemanagement.key.pub"


# we will use a simple dictionary with hostname as key
# to manage our host database for now
registration_db = {}
class status(Enum):
    REGISTERED = 1
    DHCPOFFER = 2
    INSTALLING = 3
    RUNNING = 4


class Host:
    """Really just a structure that keeps track of all
    information about registered hosts we are
    managing.
    """
    def __init__(self, hostname, macaddress="unknown",
                 ipaddress="unknown", profile="default",
                 status=status.RUNNING):
        self.hostname = hostname
        self.macaddress = macaddress
        self.ipaddress = ipaddress
        self.profile = profile
        self.status = status.REGISTERED

    def __str__(self):
        host_str = f"""
Host: {self.hostname}
      macaddress: {self.macaddress}
      static ip : {self.ipaddress}
      profile   : {self.profile}
      status    : {self.status}
"""
        return host_str

    def host_block(self):
        host_block = f"""
    host {self.hostname}
    {{
        hardware ethernet {self.macaddress};
        fixed-address {self.ipaddress};
        # cloudstack profile {self.profile};
        option routers {router_ip};
        option domain-name-servers {dns_servers};
        filename "{pxefilename}";
    }}
"""
        return host_block

    def macaddress_file(self):
        """pxeboot needs a macaddress in this format:
                11:22:33:44:55:66
        to correspond to a file name like this:
             01-11-22-33-44-55-66
        (for some reason pxeboot prepends 01 on these file
        file names)
        """
        macaddress_file = self.macaddress.replace(':', '-')
        macaddress_file = f"01-{macaddress_file}"
        return macaddress_file


def read_host_registration():
    """Parse the host registration file.  This file keeps track of
    all host information for hosts being managed in our cloudstack
    (or other) cluster. 

    We are currently using the dhcpd.conf file to keep track of
    managed host information.  This may be inadequate for more
    advanced needs.  We use simple regular expressions to
    parse, but this could be easily enhanced using a  simple
    yaml parser or equivalent here.
    """
    current_host = None
    for line in open(registration_file).readlines():
        # search for a host block, all options read
        # from subsequent lines pertain to this host until
        # we see the next host block
        pattern = re.compile(r"^\s*host\s+(\w+).*$")
        match = pattern.match(line)
        if match:
            hostname = match.group(1)
            #print("Parsing host: <%s>" % (hostname))
            current_host = Host(hostname)
            registration_db[hostname] = current_host

        # search for hardware ethernet mac address
        mac_pattern = "..:..:..:..:..:.."
        pattern = re.compile(r"^\s*hardware\s+ethernet\s+(%s);.*$" % (mac_pattern))
        match = pattern.match(line)
        if match:
            macaddress = match.group(1)
            #print("    matched mac address: <%s>" % (macaddress))
            current_host.macaddress = macaddress

        # search for static ip address assignment
        ip_pattern = "\d+\.\d+\.\d+\.\d+"
        pattern = re.compile(r"^\s*fixed-address\s+(%s);.*$" % (ip_pattern))
        match = pattern.match(line)
        if match:
            ipaddress = match.group(1)
            #print("    matched ip address: <%s>" % (ipaddress))
            current_host.ipaddress = ipaddress

        # search for cloudstack profile assignment
        pattern = re.compile(r"^\s*\#*\s*cloudstack\s+profile\s+(\w+);.*$")
        match = pattern.match(line)
        if match:
            profile = match.group(1)
            #print("    matched profile: <%s>" % (profile))
            current_host.profile = profile

    print("======== Read Host Registration ========")
    print("The list of registered hosts discovered")
    for hostname in registration_db:
        print(registration_db[hostname])
    print("")
    

def follow_system_events_file():
    """From: https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf
    Setup up generator that seeks to end of file and yields new
    lines as they are logged.
    """
    # open the systems events file (syslog)
    systemfile = open(system_event_file)
    
    # seek the end of the file
    systemfile.seek(0, os.SEEK_END)

    # start infinite loop
    while True:
        # read last line of file
        line = systemfile.readline()

        # sleep if file hasn't been updated
        if not line:
            time.sleep(0.5)
            continue

        yield line


def is_registered(macaddress):
    """Return true if we already have this macaddress registered as
    a cloudstack cluster host, false if not.
    """
    hostname = lookup_host_by_mac(macaddress)

    if hostname:
        return True
    else:
        return False

    
def lookup_host_by_mac(macaddress):
    """Search registration database to see if the given
    macaddress is already registered or not.
    """
    # return first hostname found registered with that macaddress
    for hostname in registration_db:
        if registration_db[hostname].macaddress == macaddress:
            return hostname

    # indicate failure by returning None
    return None


def lookup_host_by_ipaddress(ipaddress):
    """Search registration database to see if the given
    ipaddress is already registered or not.
    """
    # return first hostname found registered with that macaddress
    for hostname in registration_db:
        if registration_db[hostname].ipaddress == ipaddress:
            return hostname

    # indicate failure by returning None
    return None


def create_bootconfig_file(hostname):
    """A new host has been registered for this cluster.  Create the
    host pxelinux boot configuration file using the information 
    gathered for this host.

    TODO: we really should be using something like j2 templates
    here and everywhere instead of cluttering up code with
    multi line strings.
    """
    # lookup host in registration database
    host = registration_db[hostname]
    bootconfig_file = f"{pxelinux_config_dir}/{host.macaddress_file()}"
    #new_bootconfig_file = f"./{host.macaddress_file()}"
    
    print("======== Create pxeboot configuration file ========")
    print(f"    ----- creating boot configuration for mac: {host.macaddress}")
    print(f"    -----                            hostname: {host.hostname}")
    print(f"    -----                            filename: {bootconfig_file}")
    print("")
    
    # open new bootconfig file
    file = open(bootconfig_file, 'w')

    # write the global settings preamble
    bootconfig_preamble = """
ONTIMEOUT install
timeout 30
prompt 1

display boot.msg

MENU TITLE PXE Menu

"""
    file.write(bootconfig_preamble)
    
    # write the install-server menu label
    menu_install_server = """
LABEL install
  MENU LABEL ^Install Ubuntu 22.04 Live Server
  kernel vmlinuz
  initrd initrd
"""
    file.write(menu_install_server)

    # create the autoinstall on boot information line
    append = f"  append url=http://{apache_server_ip}/images/{iso_image_name} autoinstall ds=nocloud-net;s=http://{apache_server_ip}/ks/{host.hostname}/ cloud-config-url=/dev/null ip=dhcp fsck.mode=skip ---"
    file.write(append)

    # create the boot from local drive menu
    menu_boot_local = """

LABEL local
  MENU LABEL ^Boot from local drive
  LOCALBOOT 0

"""
    file.write(menu_boot_local)
    file.close()

    # use sudo root authentication to copy the new file to its correct
    # location
    #command = f"cp {new_bootconfig_file} {bootconfig_file}"
    #subprocess.run(command, shell=True)
    
    # make a symbolic link to this file but using the host name, which
    # makes it much easier for humans to find the bootconfig
    bootconfig_link = f"{pxelinux_config_dir}/{host.hostname}"
    command = f"ln -rs {bootconfig_file} {bootconfig_link}"
    subprocess.run(command, shell=True)


def create_host_kickstart_file(hostname):
    """Create a host kickstart file from the profile registered for
    this host.
    """
    # lookup host in registration database
    host = registration_db[hostname]
    ks_profile = f"{ks_profile_dir}/{host.profile}"
    ks_config = f"{ks_config_dir}/{host.hostname}"
    user_data_file = f"{ks_config}/user-data"
    
    print("======== Create kickstart files ========")
    print(f"    ----- creating kickstart files for : {host.hostname}")
    print(f"    -----                 using profile: {host.profile}")
    print(f"    -----                  profile name: {ks_profile}")
    print(f"    -----                kickstart name: {user_data_file}")
    
    # copy the configuration to the new kickstart registration
    # we can't use links as we need to modify information in each
    # separate ks configuration user-data file
    command = f"cp -r {ks_profile} {ks_config}"
    subprocess.run(command, shell=True)

    # make the modifications to the new user_data file
    # update hostname
    command = f"sed -i 's/    hostname: fixmehostname.*/    hostname: {host.hostname}/g' {user_data_file}"
    subprocess.run(command, shell=True)
    
    # update ip address
    command = f"sed -i 's|        addresses: \[fixmeipaddress\].*|        addresses: [{host.ipaddress}/24]|g' {user_data_file}"
    subprocess.run(command, shell=True)

    # inject ansible management key into cloudstack user
    key = open(ansible_manager_key).readlines()[0].strip()
    key = f'\"{key}\"'
    print(f"    ---- inserting ansible manager key: {key}")
    print("")
    command = f"sed -i 's/    authorized-keys: \[fixmekey\].*/    authorized-keys: [{key}]/g' {user_data_file}"
    subprocess.run(command, shell=True)

    # TODO: this is getting kludgy, as a result of trying to move
    #    location of served files to own directory, need to have permissions
    #    exactly correct.  This needs to be run after the sed updates?
    command = f"sudo chown -R dash:www-data {ks_config}"
    subprocess.run(command, shell=True)
    
    
def update_registration_file():
    """Write out a new registration database configuration to them
    dhcpd.conf file that we are using to maintain our cloudstack
    cluster host registration information in.

    We recreate the whole file with all registered hosts entered
    to make this routine simple.
    """
    print("======== Update dhcpd.conf registration file ========")
    print("")
    new_registration_file = "./dhcpd.conf"

    # we will rewrite this whole file everytime we update it.
    # (re)open file for writing, destroying past configuration
    file = open(new_registration_file, 'w')
    
    # first output the global dhcp configuration needed in file header
    file.write(dhcp_conf_settings)

    # create the subnet information we are monitoring hosts on
    file.write("subnet %s netmask %s\n" % (subnet, netmask))
    file.write("{\n")

    # now iterate over the hostnames in order and output a host
    # block for each one we have registered under our management
    hosts = sorted(registration_db.keys())
    for hostname in hosts:
        host = registration_db[hostname]
        file.write(host.host_block())
        
    # close the subnet block of the file
    file.write("}\n")
    file.close()

    # now use sudo root authentication to copy the updated
    # dhcpd.conf / registration to correct location
    command = f"sudo cp {new_registration_file} {registration_file}"
    subprocess.run(command, shell=True)


def register_host(macaddress):
    """When a dhcpd offer is detected, we will attempt to register the
    detected host into our cluster.  The mac_address that was received
    is given as input. 

    We first check if the host is already registered, if it is we do nothing.

    If the host is not registered, we ask the user if they want to register
    the machine.  If so we gather the information we need to register the
    machine and return.
    """
    # ignore already registered hosts
    if is_registered(macaddress):
        hostname = lookup_host_by_mac(macaddress)
        print("    not registering macaddress: <%s> already registered as host: <%s>" %
              (macaddress, hostname))
        return

    # otherwise see if we should register this new host
    answer = input("    new host detected macaddress <%s> should we register this host (y/n): " %(macaddress))
    yes_responses = ['y', 'Y', 'yes', 'Yes', 'YES']
    if answer in yes_responses:
        hostname =  input("    enter hostname: ")
        ipaddress = input("    enter static ip for host: ")
        profile =   input("    enter host installation profile: ")
        print("")
        
        host = Host(hostname, macaddress, ipaddress, profile, status.DHCPOFFER)
        registration_db[hostname] = host

        # create autoinstall boot configuration in anticipation of the
        # newly registered host performing an autoinstall boot
        create_bootconfig_file(hostname)

        # TODO: create user-data file
        # The hostname and ip address are the only things that need to change
        # in the user-data?  Maybe copy from the profile to ks/hostname/
        # then do search and replace on those properties
        create_host_kickstart_file(hostname)
        
        # now update dhcpd server with new manged host configurations
        # and reload dhcpd service with new configuration
        update_registration_file()
        restart_dhcpd_service()

        # keep track of the state of this host
        host.status = status.DHCPOFFER


def set_host_local_boot(hostname):
    """Configure the given hosts pxeboot config file to default to
    a local disk boot on its next network boot.
    """
    # lookup host in registration database
    host = registration_db[hostname]

    print(f"    -------- setting host {host.hostname} to perform local boot on reboot")
    print("")
    
    # determine boot configuration file name
    bootconfig_file = f"{pxelinux_config_dir}/{host.macaddress_file()}"

    # we will use a simple bash sed replace line infile, switching
    # to sudo authority for the command
    command = f"sed -i 's/ONTIMEOUT.*/ONTIMEOUT local/g' {bootconfig_file}"
    subprocess.run(command, shell=True)

    
def install_host(ipaddress):
    """A host that was assigned the given ip address has begun an
    autoinstall boot.  Update the bootconfig file for that host so
    that when they complete and reboot, they don't begin an install
    again in an endless loop.
    """
    # look up the host in our registered hosts
    hostname = lookup_host_by_ipaddress(ipaddress)

    if not hostname:
        print(f"    WARNING: host at {ipaddress} appears to be boot autoinstalling but it is not registered")
        return
    
    print("======== Host performing pxeboot autoinstall ========")
    print(f"    -------- detected pxeboot autoinstall for host {hostname} by ip address {ipaddress}")
    # get a handle on the host and update it
    host = registration_db[hostname]
    if host.status != status.DHCPOFFER:
        print(f"    WARNING: host {host.hostname} was not in expected state when we detected it performing boot autoinstall")
    host.status = status.INSTALLING

    # the host is currently boot autoinstalling.  set pxe bootconfig menu
    # to automatically boot to the local disk on reboot
    set_host_local_boot(hostname)
    
    
def monitor_host_registrations():
    """Begin monitoring syslog for DHCPDISCOVER requests.
    A node when netbooted will make a DHCPDISCOVER to try
    and be assigned its ip addanss.  If we see a discover
    request, it may be from a node we are trying to register
    to be managed by this cluster.

    We will ask the user if they want to register.  If they
    do then we gather
        - hostname
        - static ip assignment
    Then we have to update the registration database, and update
    the dhcp configuration and reload dhcpd configuration.

    This method runs until the user quits the registration.

    TODO: we may want/need asynchronous monitoring here, so we can
       either prompt user when we discover an event needing input
       asynchronously, or allow the user to quit the monitoring
       once done.
    """
    print("======== Monotor Syslog for Host Registration Requests ========")
    global registration_done
    systemevent = follow_system_events_file()
    
    # iterate over the lines
    print("    -------- async monitor system events starting")
    print("")
    print("    use ctrl-c to end host registration cleanly")
    print("")
    while not registration_done:
        # get next system event
        line = next(systemevent)

        # determine if a DHCPDISCOVER was received
        mac_pattern = "..:..:..:..:..:.."        
        pattern = re.compile(r"^.*DHCPDISCOVER\s+from\s+(%s).*$" % (mac_pattern))
        match = pattern.match(line)
        
        # if offer received, gather information from operator
        # to see how we should register this machine
        if match:
            macaddress = match.group(1)
            print("")
            print("    detected DHCPDISCOVER from macaddress: <%s>" % macaddress)
            register_host(macaddress)

        # determine if registerd host install has begun
        ip_pattern = "\d+\.\d+\.\d+\.\d+"
        pattern = re.compile(f"^.*RRQ\s+from\s+({ip_pattern})\s+filename\s+initrd.*$")
        match = pattern.match(line)

        # if an initrd file was requested, the host is doing an autoinstall
        if match:
            ipaddress = match.group(1)
            print("")
            #print(f"    detected autoinstall in progress from ipaddress: <{ipaddress}>")
            install_host(ipaddress)
        
    print("    -------- finishing host registration")


def end_registration_handler(signum, frame):
    print("    -------- user has ended host registration")
    global registration_done
    registration_done = True


def restart_services():
    """(re)Start the services needed for cluster host registration.
    We usually need dhcpd, tftpd and apache2 services running.
    On the ansible management machine it is not normal to have these
    running continuously, only when we are registering or 
    reinstalling hosts.

    We restart in case somehow they are already running, to
    ensure that their config files are reloaded.

    NOTE: we use sudo root escalation here, so this requires
    that this script be run as root or as an sudo enabled user.
    """
    print("======== Start registration services ========")
    for service_name in service_list:
        print("    -------- starting service %s" % (service_name))
        command = "sudo systemctl restart %s" % (service_name)
        subprocess.run(command, shell=True)
    print("")


def restart_dhcpd_service():
    """Retart the dhcpd service.  Ensure it is running on this machine.
    """
    print("======== Restart dhcpd service ========")
    print("    -------- restarting service %s" % (dhcpd_service_name))
    command = "sudo systemctl restart %s" % (dhcpd_service_name)
    subprocess.run(command, shell=True)
    print("")


def stop_services():
    """Stop the services needed for cluster host registration.
    It is normal that we usually only have these running on
    the ansible management machine when we are doing
    registrations or reinstalls.

    NOTE: we use sudo root escalation here, so this requires
    that this script be run as root or as an sudo enabled user.
    """
    print("======== Stop registration services ========")
    for service_name in service_list:
        print("    -------- stopping service %s" % (service_name))
        command = "sudo systemctl stop %s" % (service_name)
        subprocess.run(command, shell=True)
    print("")


def main():
    """Script main function.
    """
    # do we need any command line arguments, do command line
    # parsing here if we decide.

    # 1. read in and determine database of currently registered hosts
    read_host_registration()

    # 2. ensure dhcpd and tftpd servers are up and running,
    #    normal state is to have them turned off unless we are
    #    registering or reinstalling machines
    restart_services()

    # 3. begin monitoring syslog for DHCPDISCOVER events, which may
    #    indicate a new network book of a machine we want to register
    #    for this cluster
    # setup asynchronous signal to let user cleanly notify when registration
    # should end
    signal.signal(signal.SIGINT, end_registration_handler)
    registration_done = False
    monitor_host_registrations()

    print("======== Registration Finished ========")
    print("The full list of registered hosts")
    for hostname in registration_db:
        print(registration_db[hostname])
    
    # X. registration finished, turn dhcp and tftp server back off
    stop_services()

if __name__ == "__main__":
    main()
