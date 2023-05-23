# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).



## [0.1] - 2023-05-23 Release 0.1 pxemanage basic functionality

### Added

This release marks a milestone for the pxemanage subproject
functionality.  The pxamanage code is intended to allow one to easily
use pxelinux netboot to autoinstall host machines in a cluster.  The
subproject has 3 scripts currently

- register-hosts
- reinstall-hosts
- unregister-hosts

The system uses and controls 3 system services to perform the tasks of
installing nodes semi-automatically over network boots.  dhcpd is used
to detect the initial boot of an unregistered host and gather
information and associate it with the host with how it will be managed
in the cluster (basically the hostname and ip address).  tftp and http
are used by netboot autoinstall processes to serve the image files and
install media.  tftp has initial boot configuration, while http serves
iso install image and has cloud-init kickstarter files.

