#! /usr/bin/env python3
"""This script is a command line tool that is used to force reboot and
a clean reinstallation of host nodes under management in a cluster.
This script sets the pxeboot configuration to perform a reinstall on
next boot, and then tries to perform a ssh reboot of the indicated
node.  It monitors the syslog to see if it detects that a node has
begun an auto (re)install.  If it sees the node reinstalling, it
resets their pxeboot configuration to go back to normal boot from the
local hard drive on next boot.  This script exits when all hosts have
(begun) install and have the pxe config set back correctly to a local
boot on next reboot.

This script needs to modify root configuration files and
start and stop root services, it uses sudo privilage
escalation where needed.  The user it is run as
needs to have sudo privileges on the host to successfully
run this script.
"""
import argparse
import signal
import sys
# load pxemanage routines into local namespace
from pxemanage import \
    load_host_registration, \
    configure_hosts_for_reinstall, \
    reboot_hosts, \
    monitor_host_reinstalls, \
    restart_services, \
    stop_services, \
    hosts, \
    status


usage_msg = """Cause the given hosts to be forced to reboot and perform a netbook
autoinstall to reinstall their systems.  Hosts must be under
management of this cluster and registered previously in the cluster
management host database.  All hosts are assumeed to have root/sudo
ssh access to them so that they can be forcably rebooted.

NOTE: this script does not attempt to vacate any virtual machines or
virtual data storage currently being used on the hosts.  It is best
practice to attempt to vacate virtual instances from hosts before
rebooting and reinstalling them.  """


def end_reinstall_handler(signum, frame):
    """This function is registered as a signal handler for an interupt
    (SIGINT ctrl-c) signal.  We first try and determine if it appears 
    all hosts have begun reinstall.  If it doesn't appear hosts have
    started reinstall, then we may not have set the reboot action 
    back to normal local hard drive boot, so we warn users and give
    option to continue monitoring.

    Parameters
    ----------
    signum - the signal number of the generated interupt. If we register only for
       for ctrl-c (SIGINT) signals, this should be 2 (we could/should check it?)
    frame - current stack frame, not used here.
    """
    print("    -------- user has ended host reinstallation monitoring")
    # check if any machine still in dhcp offer state
    for hostname in hosts:
        if hosts[hostname].status ==  status.REBOOTING:
            print("    Warning, 1 or more hosts detected still in REBOOTING status.")
            print("    This means machine was rebooted but we haven't seen")
            print("    installation begin.  If you end registration now, the")
            print("    machines bootconfig may still be set to reinstall on boot.")
            print(f"   host: {hostname} status: {hosts[hostname].status}")
            yes_responses = ['y', 'Y', 'yes', 'Yes', 'YES']
            answer = input("Do you really want to end reinstallation monitoring now (y/n): ")
            # if not a yes we can return and continue registering
            if not answer in yes_responses:
                return

    # stop the installation monitoring
    print("======== Reinstallation Finished ========")
    print("The full list of registered hosts")
    for hostname in hosts:
        print(hosts[hostname])

    # stop the pexmanagement services
    stop_services()
    sys.exit(0)


def main():
    """Script main function.
    """
    # 0. parse command line arguments to get list of hosts to
    # reinstall
    parser = argparse.ArgumentParser(prog='reinstall-hosts', description=usage_msg)
    parser.add_argument('hostname', type=str, nargs='+',
                        help='one or more hosts to attempt to reboot and reinstall')
    args = parser.parse_args()
    
    # 1. read in and determine database of currently registered hosts
    load_host_registration()

    # 2. ensure dhcpd and tftpd servers are up and running,
    #    normal state is to have them turned off unless we are
    #    registering or reinstalling machines
    restart_services()

    # 3. set all hosts to perform reinstall on network boot
    #    this method also validates the hostnames and only returns
    #    valid managed hosts to attempt further actions with
    hostnames = configure_hosts_for_reinstall(args.hostname)

    # 4. attempt to reboot all hosts to start the reinstallation
    #    process
    reboot_hosts(hostnames)
    
    # 5. monitor the system events to attempt to detect when
    #    hosts have begun their installation.  We end when
    #    all hosts reach installing/running status, or when
    #    user performs sigint
    signal.signal(signal.SIGINT, end_reinstall_handler)
    monitor_host_reinstalls()

    
if __name__ == "__main__":
    main()
