"""
pxemanage module

Contents
--------

This package contains functions for managing pxe autoinstall
boots and reinstalls of host machines.  It is mainly
targeted at easilty setting up a rack/cluster of machines
with basic os image, and doing just enough configuration
to allow for ssh access and ansible management of the hosts
thereafter.  This package controls 3 system services,
dhcpd, tftpd and apache2 (or other web server) to
manage pxe network boots.
"""
from enum import Enum
from jinja2 import Environment, FileSystemLoader

# these are the submodule imports for the pxemanage module
from .bootconfig import *
from .config import settings
from .db import *
from .kickstart import *
from .register import *
from .services import *


# jinja2 templates
j2 = Environment(loader=FileSystemLoader("templates/"))
