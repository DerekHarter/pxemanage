"""pxemanage module

register submodule

Contents
--------

Functions relating to implementation of host registration
(e.g. register-hosts script).  We monitor the system events file
(syslog) for events that indicate the progress/status of hosts.

DHCPDISCOVER: indicates a potential new host for the cluster was
  started and is attempting a net boot.  We determine if we want to
  register this machine, and if so we assign it its name, ip address
  and profile in the cluster we are managing.

tftp RRQ for initrd file: When a machine is performing a netboot
  autoinstall, it needs to load the pxelinux.0, initrd and vmlinuz
  files from the tftp server (among others).  When the initrd files is
  requested, it is about to begin its install process in earnest.  We
  use this event as an indication that the machine is installing
  itself currently.

"""
import os
import re
import sys
import time
import pxemanage as pm


def monitor_host_registrations():
    """Begin monitoring syslog for DHCPDISCOVER requests.  A node when
    netbooted will make a DHCPDISCOVER to try and be assigned its ip
    addanss.  If we see a discover request, it may be from a node we
    are trying to register to be managed by this cluster.

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
    systemevent = follow_system_events_file()
    
    # iterate over the lines
    print("    -------- async monitor system events starting")
    print("")
    print("    use ctrl-c to end host registration cleanly")
    print("")
    while True:
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
            pm.register_host(macaddress)

        # determine if registerd host install has begun
        ip_pattern = "\d+\.\d+\.\d+\.\d+"
        pattern = re.compile(f"^.*RRQ\s+from\s+({ip_pattern})\s+filename\s+initrd.*$")
        match = pattern.match(line)

        # if an initrd file was requested, the host is doing an autoinstall
        if match:
            ipaddress = match.group(1)
            #print(f"    detected autoinstall in progress from ipaddress: <{ipaddress}>")
            pm.install_host(ipaddress)

    # actually cannot currently get here, there is no way to stop monitoring for
    # registration until the user tells us that registration is done
    print("    -------- finishing host registration")
    pm.stop_services()


def follow_system_events_file():
    """From: https://medium.com/@aliasav/how-follow-a-file-in-python-tail-f-in-python-bca026a901cf
    Setup up generator that seeks to end of file and yields new
    lines as they are logged.  This work by actually never returning, if it performs
    a read but the file is at the end of the file, it sleeps a bit and trys to keep
    reading again. readline() python module can handle this and will keep reading 
    new lines at the end of the file as they appear in the log.

    Returns
    -------
    system event string - Each yield retuns a line from the system events
       log (syslog), as soon as it become available.
    """
    # open the systems events file (syslog)
    systemfile = open(pm.settings['system_event_file'])
    
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


def register_host(macaddress):
    """When a dhcpd offer is detected, we will attempt to register the
    detected host into our cluster.  The mac_address that was received
    is given as input.

    We first check if the host is already registered, if it is we do nothing.

    If the host is not registered, we ask the user if they want to register
    the machine.  If so we gather the information we need to register the
    machine and return.

    TODO: add command line options to allow for auto sequence registrations,
    e.g. first host get number 01, name cloud01 and ip 192.168.0.1...

    Parameters
    ----------
    macaddress - The hardware mac address of the machine that was
      detected asking for a dhcp lease offer.
    """
    # ignore already registered hosts
    if pm.is_registered(macaddress):
        hostname = pm.lookup_host_by_mac(macaddress)
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
        
        host = pm.Host(hostname, macaddress, ipaddress, profile, pm.status.DHCPOFFER)
        pm.hosts[hostname] = host

        # create autoinstall boot configuration in anticipation of the
        # newly registered host performing an autoinstall boot
        pm.create_bootconfig_file(hostname)

        # TODO: create user-data file
        # The hostname and ip address are the only things that need to change
        # in the user-data?  Maybe copy from the profile to ks/hostname/
        # then do search and replace on those properties
        pm.create_kickstart_file(hostname)
        
        # now update dhcpd server with new manged host configurations
        # and reload dhcpd service with new configuration
        pm.update_host_registration()
        pm.restart_dhcpd_service()

        # keep track of the state of this host
        host.status = pm.status.DHCPOFFER


def install_host(ipaddress):
    """A host that was assigned the given ip address has begun an
    autoinstall boot.  Update the bootconfig file for that host so
    that when they complete and reboot, they don't begin an install
    again in an endless loop.

    Parameters
    ----------
    ipaddress - The ip (internet protocol) address of the host were an
      install in progress was detected.
    """
    # look up the host in our registered hosts
    hostname = pm.lookup_host_by_ipaddress(ipaddress)
    if not hostname:
        print(f"    WARNING: host at {ipaddress} appears to be boot autoinstalling but it is not registered")
        return
    
    print("======== Host performing pxeboot autoinstall ========")
    print(f"    -------- detected pxeboot autoinstall for host {hostname} ip address {ipaddress}")
    
    # get a handle on the host and update it
    host = pm.hosts[hostname]
    if not (host.status == pm.status.DHCPOFFER or host.status == pm.status.REBOOTING):
        print(f"    WARNING: host {host.hostname} was not in expected state when we detected it performing boot autoinstall")
    host.status = pm.status.INSTALLING

    # the host is currently boot autoinstalling.  set pxe bootconfig menu
    # to automatically boot to the local disk on reboot
    pm.set_host_local_boot(hostname)
