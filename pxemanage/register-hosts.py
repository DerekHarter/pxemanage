#! /usr/bin/env python3
"""This script is a command line tool that is used to register
new cloudstack hosts.  This script manages dhcpd and tftpd
resources to detect new dhcp requests, register the hosts
by adding them into the dhcp services, then set the hosts
up to perform a autoinstall network boot.

This script needs to modify root configuration files and
start and stop root services, it uses sudo privilage
escalation where needed.  The user it is run as
needs to have sudo privileges on the host to successfully
run this script.
"""
import argparse
import signal
import signal
# load pxemanage routines into local namespace
from pxemanage import \
    load_host_registration, \
    monitor_host_registrations, \
    restart_services, \
    stop_services, \
    hosts, \
    status


usage_msg = """Register new hosts to be put under management
for our cluster.  A host being under management means we
assign a host name and a static ip address for the bare 
metal OS node configuration.  We manage hosts using
pxelinux netboot to autoinstall and reinstall nodes
when needed.
"""

def end_registration_handler(signum, frame):
    """This function is registered as a signal handler for an interupt
    (SIGINT ctrl-c) signal.  We notify the main loop that the user
    want to end registration.

    Parameters
    ----------
    signum - the signal number of the generated interupt. If we register only for
       for ctrl-c (SIGINT) signals, this should be 2 (we could/should check it?)
    frame - current stack frame, not used here.

    """
    print("    -------- user has ended host registration")
    # check if any machine still in dhcp offer state
    for hostname in hosts:
        host_status = hosts[hostname].status
        if host_status == status.DHCPOFFER or host_status == status.REGISTERED:
            print("    Warning, 1 or more hosts detected still in DHCPOFFER status.")
            print("    This means machine was registered but not yet installed.")
            print("    If you end registration now, the machines bootconfig may")
            print("    still be set to reinstall on boot")
            print(f"   host: {hostname} status: {host_status}")
            yes_responses = ['y', 'Y', 'yes', 'Yes', 'YES']
            answer = input("Do you really want to end registration now (y/n): ")
            # if not a yes we can return and continue registering
            if not answer in yes_responses:
                return

    # stop the registration
    print("======== Registration Finished ========")
    print("The full list of registered hosts")
    for hostname in hosts:
        print(hosts[hostname])

    # stop the services
    stop_services()
    sys.exit(0)


def main():
    """Script main function.

    TODO: add command line parsing for sequence auto registers,
      logging output verbosity, what else?
    """
    # 0. parse command line arguments.
    # TODO: could/should add options to auto register, e.g.
    # give base hostname (cloud-1-%02d) and
    # base ip address (192.168.0.%d) and auto name and number
    # hosts as their dhcp offers come in
    parser = argparse.ArgumentParser(prog='register-hosts', description=usage_msg)
    #parser.add_argument('autoregister', type=bool, nargs='+',
    #                    help='')
    args = parser.parse_args()
    
    # 1. read in and determine database of currently registered hosts
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

    
if __name__ == "__main__":
    main()
