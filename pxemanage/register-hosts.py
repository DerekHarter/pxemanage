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
import signal
# load pxemanage routines into local namespace
from pxemanage import \
    load_host_registration, \
    monitor_host_registrations, \
    end_registration_handler, \
    restart_services, \
    stop_services


def main():
    """Script main function.

    TODO: add command line parsing for sequence auto registers,
      logging output verbosity, what else?
    """
    # do we need any command line arguments, do command line
    # parsing here if we decide.

    # 1. read in and determine database of currently registered hosts
    print(dir())
    load_host_registration()

    # 2. ensure dhcpd and tftpd servers are up and running,
    #    normal state is to have them turned off unless we are
    #    registering or reinstalling machines
    restart_services()

    # 3. begin monitoring syslog for DHCPDISCOVER events, which may
    #    indicate a new network book of a machine we want to register
    #    for this cluster
    #
    #    Setup asynchronous signal to let user cleanly notify when
    #    registration should end
    signal.signal(signal.SIGINT, end_registration_handler)
    monitor_host_registrations()

    # 4. registration finished, turn dhcp and tftp server back off
    stop_services()

    
if __name__ == "__main__":
    main()
