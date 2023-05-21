#! /usr/bin/env python3
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
from config import settings
from enum import Enum
from jinja2 import Environment, FileSystemLoader


# system globals
registration_done = False

# jinja2 templates
j2 = Environment(loader=FileSystemLoader("templates/"))

# we will use a simple dictionary with hostname as key
# to manage our host database for now
hosts = {}


class status(Enum):
    REGISTERED = 1
    DHCPOFFER = 2
    INSTALLING = 3
    RUNNING = 4


class Host(dict):
    """Really just a structure that keeps track of all
    information about registered hosts we are
    managing.

    Actually this class is a dict so that we can
    easily pass into j2 to render templates.  But
    it can act like a struct because we override the
    getattr method.
    """
    def __init__(self, hostname, macaddress="unknown",
                 ipaddress="unknown", profile="default",
                 status=status.RUNNING):
        self.hostname = hostname
        self.macaddress = macaddress
        self.ipaddress = ipaddress
        self.profile = profile
        self.status = status

    def __str__(self):
        host_str = f"""
Host: {self.hostname}
      macaddress: {self.macaddress}
      static ip : {self.ipaddress}
      profile   : {self.profile}
      status    : {self.status}
"""
        return host_str

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

    def __getattr__(self, name):
        """Overload member access (getting an attribute) so that we
        can perform host.ipaddress and have it lookup the value for
        the key for us.
        """
        return self.__getitem__(name)
    

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
    for line in open(settings['registration_file']).readlines():
        # search for a host block, all options read
        # from subsequent lines pertain to this host until
        # we see the next host block
        pattern = re.compile(r"^\s*host\s+(\w+).*$")
        match = pattern.match(line)
        if match:
            hostname = match.group(1)
            #print(f"Parsing host: {hostname}")
            current_host = Host(hostname)
            hosts[hostname] = current_host

        # search for hardware ethernet mac address
        mac_pattern = "..:..:..:..:..:.."
        pattern = re.compile(f"^\s*hardware\s+ethernet\s+({mac_pattern});.*$")
        match = pattern.match(line)
        if match:
            macaddress = match.group(1)
            #print(f"    matched mac address: {macaddress}" %)
            current_host.macaddress = macaddress

        # search for static ip address assignment
        ip_pattern = "\d+\.\d+\.\d+\.\d+"
        pattern = re.compile(f"^\s*fixed-address\s+({ip_pattern});.*$")
        match = pattern.match(line)
        if match:
            ipaddress = match.group(1)
            #print(f"    matched ip address: {ipaddress}")
            current_host.ipaddress = ipaddress

        # search for cloudstack profile assignment
        pattern = re.compile(r"^\s*\#*\s*cloudstack\s+profile\s+(\w+);.*$")
        match = pattern.match(line)
        if match:
            profile = match.group(1)
            #print(f"    matched profile: {profile}")
            current_host.profile = profile

    print("======== Read Host Registration ========")
    print("The list of registered hosts discovered")
    for hostname in hosts:
        print(hosts[hostname])
    print("")


def follow_system_events_file():
    """From: https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf
    Setup up generator that seeks to end of file and yields new
    lines as they are logged.
    """
    # open the systems events file (syslog)
    systemfile = open(settings['system_event_file'])
    
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
    for hostname in hosts:
        if hosts[hostname].macaddress == macaddress:
            return hostname

    # indicate failure by returning None
    return None


def lookup_host_by_ipaddress(ipaddress):
    """Search registration database to see if the given
    ipaddress is already registered or not.
    """
    # return first hostname found registered with that macaddress
    for hostname in hosts:
        if hosts[hostname].ipaddress == ipaddress:
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
    host = hosts[hostname]
    bootconfig_file = f"{settings['pxelinux_config_dir']}/{host.macaddress_file()}"
    
    print("======== Create pxeboot configuration file ========")
    print(f"    ----- creating boot configuration for mac: {host.macaddress}")
    print(f"    -----                            hostname: {host.hostname}")
    print(f"    -----                            filename: {bootconfig_file}")
    print("")

    # get template and render
    template = j2.get_template("pxeboot.cfg.j2")
    content = template.render(hostname = hostname,
                              apache_server_ip = settings['apache_server_ip'],
                              iso_image_name = settings['iso_image_name'])
    file = open(bootconfig_file, mode="w")
    file.write(content)
    file.close()
    
    # make a symbolic link to this file but using the host name, which
    # makes it much easier for humans to find the bootconfig
    bootconfig_link = f"{settings['pxelinux_config_dir']}/{host.hostname}"
    command = f"ln -rs {bootconfig_file} {bootconfig_link}"
    subprocess.run(command, shell=True)


def create_host_kickstart_file(hostname):
    """Create a host kickstart file from the profile registered for
    this host.
    """
    # lookup host in registration database
    host = hosts[hostname]
    ks_config = f"{settings['ks_config_dir']}/{host.hostname}"
    
    print("======== Create kickstart files ========")
    print(f"    ----- creating kickstart files for : {host.hostname}")
    print(f"    -----                 using profile: {host.profile}")
    print(f"    -----                kickstart name: {ks_config}")

    # create new subdirectory in ks hierarchy to hold this hosts kickstart file
    command = f"mkdir -p {ks_config}"
    subprocess.run(command, shell=True)

    # get user-data template and render it contents
    # TODO: we should probably render the gateway and name servers
    #   into the user-data here as well.
    management_key = open(settings['ansible_manager_key']).readlines()[0].strip()
    management_key = f'"{management_key}"'
    template = j2.get_template(f"profiles/{host.profile}/user-data.j2")
    content = template.render(hostname = host.hostname,
                              ipaddress = host.ipaddress,
                              management_key = management_key)
    file = open(f"{ks_config}/user-data", mode="w")
    file.write(content)
    file.close()
        
    # copy the meta-data file from profile, these currently don't
    # have any templates to render, but we'll keep in just in case
    template = j2.get_template(f"profiles/{host.profile}/meta-data.j2")
    content = template.render()
    file = open(f"{ks_config}/meta-data", mode="w")
    file.write(content)
    file.close()

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

    # get dhcpd.conf template and render its contents
    # TODO: should templatize the router and dns information
    #   in this template as well.
    template = j2.get_template("dhcpd.conf.j2")
    content = template.render(hosts=hosts)
    file = open(f"{new_registration_file}", mode="w")
    file.write(content)
    file.close()
    
    # now use sudo root authentication to copy the updated
    # dhcpd.conf / registration to correct location
    command = f"sudo cp {new_registration_file} {settings['registration_file']}"
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
        #print(f"    detected DHCPDISCOVER from macaddress: {macaddress}")
        #print(f"    not registering macaddress: {macaddress} already registered as host: {hostname}")
        return

    # otherwise see if we should register this new host
    print(f"    detected DHCPDISCOVER from macaddress: {macaddress}")
    answer = input(f"    new host detected macaddress {macaddress} should we register this host (y/n): ")
    yes_responses = ['y', 'Y', 'yes', 'Yes', 'YES']
    if answer in yes_responses:
        hostname =  input("    enter hostname: ")
        ipaddress = input("    enter static ip for host: ")
        profile =   input("    enter host installation profile: ")
        print("")
        
        host = Host(hostname, macaddress, ipaddress, profile, status.DHCPOFFER)
        hosts[hostname] = host

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
    host = hosts[hostname]

    print(f"    -------- setting host {host.hostname} to perform local boot on reboot")
    print("")
    
    # determine boot configuration file name
    bootconfig_file = f"{settings['pxelinux_config_dir']}/{host.macaddress_file()}"

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
    host = hosts[hostname]
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
        pattern = re.compile(f"^.*DHCPDISCOVER\s+from\s+({mac_pattern}).*$")
        match = pattern.match(line)
        
        # if offer received, gather information from operator
        # to see how we should register this machine
        if match:
            macaddress = match.group(1)
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
    """This method is registered as a signal handler for an interupt (ctrl-c)
    signal.  We notify the main loop that the user want to end registration.
    """
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
    for service_name in settings['service_list']:
        print(f"    -------- starting service {service_name}")
        command = f"sudo systemctl restart {service_name}"
        subprocess.run(command, shell=True)
    print("")


def restart_dhcpd_service():
    """Retart the dhcpd service.  Ensure it is running on this machine.
    """
    print("======== Restart dhcpd service ========")
    print(f"    -------- restarting service {settings['dhcpd_service_name']}")
    command = f"sudo systemctl restart {settings['dhcpd_service_name']}"
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
    for service_name in settings['service_list']:
        print("    -------- stopping service {service_name}")
        command = f"sudo systemctl stop {service_name}"
        subprocess.run(command, shell=True)
    print("")


def main():
    """Script main function.
    """
    # do we need any command line arguments, do command line
    # parsing here if we decide.
    global registration_done
    
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
    for hostname in hosts:
        print(hosts[hostname])

    # 4. registration finished, turn dhcp and tftp server back off
    stop_services()

    
if __name__ == "__main__":
    main()
