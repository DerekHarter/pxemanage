# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [0.1] - 2023-05-14 Release 0.1: Basic ansible cloud deployment

### Added

This release represent a significant milestone. In this release we

- have developed basic ansible playbooks and roles to perform a full small deployment
- developed scripts and procedures to automate most all end-to-end tasks from installing nodes to deploying and setting up the cloud.

## [0.2] - 2023-05-14 Release 0.2: https/ssl configuration and ansible cloudstack deployment

### Added

This release has two significant features:

1. Example of https/ssl configuration of the management UI/api
   - We have set up a self signed certificate that can be used for testing more realistic setups of https/ssl api
   - Example configuration sets up needed resources to connect with ansible cloudstack modules to provision cloud infrastructure
   - Example configuration also sets up the cloudmonkey cmk tool for api access, for performing command line scripting of cloud infrastructure
2. Example ansible playbook to provision basic cloud infrastructure setup-infrastructure.yml
   - This playbook creates a basic zone/pod/cluster, adds a guest isolated network, and adds storage pools. Example may not be completely running whole playbook without errors, but looks like the infrastructure was functional when it completed.
   - These ansible playbooks to provision cloudstack infrastructure may be as useful, if not more so, then OpenStack hot scripts that I am more familiar with.


## [0.3] - 2023-05-21 Release 0.3 pxemanage basic functionality

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

## [0.4] - 2023-05-22 Release 0.4 ssh key/cert/https/ssl authentication setup

### Added

This release is significant for pretty much having all ssh key,
CA certificate and https/ssl configuration and access working.
We create ssh keys, root and server certificates and keys.
These playbooks have examples of adding all of these
properly to get

- http/ssl access to correctly work in management web based GUI interface
- http/ssl and generated key/secret to use api in cloudstack cs tool and in
  the cloudmonkey tool
- Generating root and server certificates that correctly validate for browser
  access without errors, if we add the root CA to the list of browser
  authorities
- Set up consoleproxy and secondary storage communication to use
  https/ssl, using these certificates, so that these communications
  happen over more secure ssl connections.
- Continued with refactoring of playbooks.  Now we have two playbooks
  for initial deployment, one to deploy the cloudstack
  host/machine/baremetal infrastructure.  And the other to deploy the
  initial cloud virtual infrastructure.
- Refactor cloudstack node, management and database
  deployment into a single file.  The setup cloudstack
  playbook did not need to be a separate playbook, makes sense
  to continue configuration of management server
  after basic host setup and configuration.
