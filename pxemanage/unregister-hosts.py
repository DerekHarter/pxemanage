#! /usr/bin/env python3
"""This script is a command line tool that is used to 
unregister hosts that are currently registered and under
management in this cluster.  This script is relatively
simple, it simply removes the hosts from dhcpd management,
and removes pxeboot and kickstarter files for the specific
hosts under management.

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
    unregister_hosts


usage_msg = """Cause the given hosts to be removed from the 
database of managed hosts for this cluster.  Hosts are not
reinstalled or reformatted, that is left to the operator.  

NOTE: because the machines are not reformatted, they will still
have their static ip and hostname assignments.  If they are left
running, they may interfere with new registered hosts if given
those same identifiers.

NOTE: this script does not attempt to vacate any virtual machines or
virtual data storage currently being used on the hosts.  It is best
practice to attempt to vacate virtual instances from hosts before
rebooting and reinstalling them.  """


def main():
    """Script main function.
    """
    # 0. parse command line arguments to get list of hosts to
    # reinstall
    parser = argparse.ArgumentParser(prog='unregister-hosts', description=usage_msg)
    parser.add_argument('-a', '--all_unregister', action='store_true',
                        help='flag if set all hosts will be unregistered, this is of course dangerous')
    parser.add_argument('hostname', type=str, nargs='*',
                        help='one or more hosts to attempt to reboot and reinstall')
    args = parser.parse_args()
    
    # 1. read in and determine database of currently registered hosts
    load_host_registration()

    # 2. unregister all indicated hosts
    unregister_hosts(args.all_unregister, args.hostname)


if __name__ == "__main__":
    main()
