ice-setup
=========
A standalone setup script to install and configure different services for Ceph
like Calamari, ceph-deploy and package repositories.

.. _note: The ``ice_setup.py`` script is meant to be run within the directory
          that contains the repositories that it needs to work with. It is not
          meant to run directly.


If on the right environment (withing a directory that contains the
repositories) this script should work without a virtualenv and with Python
versions 2.6 or 2.7::

    sudo python ice_setup.py

The one requirement is to execute with ``sudo`` in the host that will have
Calamari installed, which will go through a few
steps to:

* Configure the current host for a local repository so that Calamari be
  installed, and then proceed to install it.

* Configure the current host for a local ceph-deploy repo to install
  ceph-deploy, and then procee to install it.

* Prompt the user for the FQDN and protocol (http vs https) for the current
  host so that other remote hosts can get their repo files configured to get
  packages.

* Configure the current host so that it can serve as a repository server for
  ``calamari-minions`` and ``ceph``.

This script **does not** install Ceph nor ``calamari-minions``. It will write
a ``cephdeploy.conf`` file so that ceph-deploy can read it when installing so
that less flags are needed.

This configuration file will be written to the current directory, to the ``~/``
of the current executing user (will probably be root) and if a non-root user
called the script, it will attemtp to write to that user's home dir as well.

Those files are written to all those places so that we attempt, as best as
possible, to ensure ceph-deploy will have a valid configuration file to set the
right flags to.


Installing ``calamari-minions``
-------------------------------
This script does not install the ``calamari-minions`` package, but does however
leave everything ready so that you can do it with ceph-deploy::

    ceph-deploy calamari connect {hosts}

No extra flags are needed here because the script will have created
a configuration file with the necessary metadata to create correct repo files.


Installing ``ceph``
-------------------
In similar fashion to installing ``calamari-minions``, installing ``ceph``
should not need extra information and should only need to call it with the
hosts::

    ceph-deploy install {hosts}
