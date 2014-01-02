#!/usr/bin/env python

# Copyright 2013, Inktank Storage, Inc.
# All rights reserved.
#
# This software and related documentation are provided under a license
# agreement containing restrictions on use and disclosure and are protected by
# intellectual property laws.  Except as expressly permitted in your license
# agreement or allowed by law, you may not use, copy, reproduce, translate,
# broadcast, modify, license, transmit, distribute, exhibit, perform, publish,
# or display any part, in any form, or by any means.  Reverse engineering,
# disassembly, or decompilation of this software, unless required by law for
# interoperability, is prohibited.
#
# The information contained herein is subject to change without notice and is
# not warranted to be error-free.  If you find any errors, please report them
# to us in writing.
#
# This software or hardware is developed for general use in a variety of
# information management applications.  It is not developed or intended for use
# in any inherently dangerous applications, including applications which may
# create a risk of personal injury.  If you use this software or hardware in
# dangerous applications, then you shall be responsible to take all appropriate
# fail-safe, backup, redundancy, and other measures to ensure its safe use.
# Inktank Storage, Inc.  and its affiliates disclaim any liability for any
# damages caused by use of this software or hardware in dangerous applications.

import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile


# =============================================================================
# Logging
# =============================================================================

logger = logging.getLogger('ice')

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

COLORS = {
    'WARNING': YELLOW,
    'INFO': WHITE,
    'DEBUG': BLUE,
    'CRITICAL': RED,
    'ERROR': RED
}

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

BASE_COLOR_FORMAT = "%(color_levelname)s %(message)s"
VERBOSE_COLOR_FORMAT = "[%(name)s][$BOLD%(levelname)s] $RESET%(color_levelname)s %(message)s"


def color_message(message):
    message = message.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
    return message


class ColoredFormatter(logging.Formatter):
    """
    A very basic logging formatter that not only applies color to the levels of
    the ouput but will also truncate the level names so that they do not alter
    the visuals of logging when presented on the terminal.
    """

    def __init__(self, msg):
        logging.Formatter.__init__(self, msg)

    def format(self, record):
        levelname = record.levelname
        truncated_level = record.levelname[:6]
        if levelname in COLORS:
            levelname_color = COLOR_SEQ % (30 + COLORS[levelname]) + '-->' + RESET_SEQ
            record.color_levelname = levelname_color
        return logging.Formatter.format(self, record)


def color_format(verbose=False):
    """
    Main entry point to get a colored formatter, it will use the
    BASE_FORMAT by default.
    """
    if verbose:
        color_format = color_message(VERBOSE_COLOR_FORMAT)
    else:
        color_format = color_message(BASE_COLOR_FORMAT)
    return ColoredFormatter(color_format)


# =============================================================================
# Exceptions
# =============================================================================

class ICEError(Exception):
    """Base ICE Setup exception"""
    pass


class NonZeroExit(ICEError):
    """subprocess commands that exit with non-zero status"""
    pass


class UnsupportedPlatform(ICEError):
    pass


# =============================================================================
# Templates
# =============================================================================


ice_repo_template = """
[ice]
name=ice packages for $basearch
baseurl={repo_url}/$basearch
enabled=1
gpgcheck=1
type=rpm-md
gpgkey={gpg_url}

[ice-noarch]
name=ice noarch packages
baseurl={repo_url}/noarch
enabled=1
gpgcheck=1
type=rpm-md
gpgkey={gpg_url}

[ice-source]
name=ice source packages
baseurl={repo_url}/SRPMS
enabled=0
gpgcheck=1
type=rpm-md
gpgkey={gpg_url}
"""

ice_list_template = """deb {repo_url} {codename} main\n"""


# =============================================================================
# Distributions
# =============================================================================


class CentOS(object):
    pkg_manager = Yum()


class Debian(object):
    pkg_manager = Apt()


class Fedora(object):
    pkg_manager = Yum()


class Suse(object):

    # XXX this is obviously **not** Yum, it should
    # actually be zypper. Do we want to support this?
    pkg_manager = Yum()


# Normalize casing for easier mapping
centos = CentOS
debian = Debian
fedora = Fedora
suse = Suse


def get_distro():
    """
    Retrieve the class that matches the distribution of the current host. This
    function will call ``platform()`` and retrieve the distribution
    information, then return the appropriate class and slap a few attributes
    to that class defining the information it found from the host.

    For example, if the current host is an Ubuntu server, the ``Debian`` class
    would be returned (as it holds 1:1 parity with Ubuntu) and the following
    would be set::

        module.name = 'ubuntu'
        module.release = '12.04'
        module.codename = 'precise'

    """
    distro_name, release, codename = platform_information()

    if not codename or not _get_distro(distro_name):
        error_msg = 'platform is not supported: %s %s %s' % (
            distro_name,
            release,
            codename,
        )
        raise UnsupportedPlatform(error_msg)

    # TODO: make this part of the distro objects
    # no need for them to be inferred here
    module = _get_distro(distro_name)
    module.name = distro_name
    module.release = release
    module.codename = codename
    module.machine_type = platform.machine()

    # XXX: Do we need to know about the init?
    #module.init = _choose_init(distro_name, codename)

    return module


class Yum(object):

    @classmethod
    def create_repo_file(cls, gpg_url, repo_url, file_name=None, **kw):
        """set the contents of /etc/yum.repos.d/ice.repo"""
        etc_path = kw.pop('etc_path', '/etc/yum.repos.d')
        file_name = file_name or 'ice.repo'
        repo_file_path = os.path.join(etc_path, file_name)
        with open(repo_file_path, 'w') as repo_file:
            contents = ice_repo_template.format(
                gpg_url=gpg_url,
                repo_url=repo_url,
            )
            repo_file.write(contents)

    @classmethod
    def install(cls, package):
        cmd = [
            'yum',
            '-y',
            '-q',
            'install',
        ]
        cmd.append(package)
        run(cmd)


class Apt(object):

    @classmethod
    def create_repo_file(cls, repo_url, gpg_url, file_name=None, **kw):
        """add ceph deb repo to sources.list"""
        etc_path = kw.pop('etc_path', '/etc/apt/sources.list.d')
        file_name = file_name or 'ice.list'
        list_file_path = os.path.join(etc_path, file_name)
        with open(list_file_path, 'w') as list_file:
            list_file.write(ice_list_template.format(
                repo_url=repo_url, codename=kw.pop('codename'))
            )

    @classmethod
    def install(cls, package):
        cmd = [
            'sudo',
            'env',
            'DEBIAN_FRONTEND=noninteractive',
            'apt-get',
            '-q',
            'install',
            '--assume-yes',
        ]
        cmd.append(package)
        run(cmd)


# =============================================================================
# Subprocess
# =============================================================================


def run(cmd, **kw):
    stop_on_nonzero = kw.pop('stop_on_nonzero', True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        **kw
    )

    if process.stderr:
        while True:
            err = process.stderr.readline()
            if err == '' and process.poll() is not None:
                break
            if err != '':
                logger.warning(err)
                sys.stderr.flush()
    if process.stdout:
        while True:
            out = process.stdout.readline()
            if out == '' and process.poll() is not None:
                break
            if out != '':
                logger.debug(out)
                sys.stdout.flush()

    returncode = process.wait()
    if returncode != 0:
        error_msg = "command returned non-zero exit status: %s" % returncode
        if stop_on_nonzero:
            raise NonZeroExit(error_msg)
        else:
            logger.warning(error_msg)


def run_call(cmd, **kw):
    """
    a callable that will execute a subprocess without raising an exception if
    the exit status is non-zero.

    The ``logger`` argument is in the signature only for consistency in the
    API, it does nothing by default.
    """

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw
    )
    stdout = [line.strip('\n') for line in process.stdout.readlines()]
    stderr = [line.strip('\n') for line in process.stderr.readlines()]
    return stdout, stderr, process.wait()


# =============================================================================
# System
# =============================================================================


def platform_information():
    """
    detect platform information, return a dictionary with the following keys:

    * distro_name: as in 'Ubuntu' or 'CentOS'
    * release:     like '5.0' or '13.04'
    * codename:    as in 'Wheezy' or 'Quantal'
    """
    distro, release, codename = platform.linux_distribution()

    # this could be an empty string in Debian
    if not codename and 'debian' in distro.lower():
        debian_codenames = {
            '8': 'jessie',
            '7': 'wheezy',
            '6': 'squeeze',
        }
        major_version = release.split('.')[0]
        codename = debian_codenames.get(major_version, '')
    return (
        _normalized_distro_name(distro.rstrip()),
        release.rstrip(),
        codename.rstrip(),
    )


def _get_distro(distro, fallback=None):
    if not distro:
        return

    distro = _normalized_distro_name(distro)
    distributions = {
        'debian': debian,
        'ubuntu': debian,
        'centos': centos,
        'scientific': centos,
        'redhat': centos,
        'fedora': fedora,
        'suse': suse,
        }

    return distributions.get(distro) or _get_distro(fallback)


def _normalized_distro_name(distro):
    """
    Normalizes the distribution name so it is easier to operate on well knowns
    rather than whatever small differences distributions decide to add to them
    """
    distro = distro.lower()
    if distro.startswith(('redhat', 'red hat')):
        return 'redhat'
    elif distro.startswith(('scientific', 'scientific linux')):
        return 'scientific'
    elif distro.startswith(('suse', 'opensuse')):
        return 'suse'
    return distro


# =============================================================================
# File Utilities
# =============================================================================

def extract_file(file_path):
    """
    Decompress/Extract a tar file to a temporary location and return its full
    path so that it can be handled elsewhere.  If ``file_path`` is not a tar
    file and it is a directory holding decompressed files return ``file_path``,
    otherwise raise an error.

    Removal of the temporary directory files is responsibility of the caller.
    """
    if os.path.isdir(file_path):
        return file_path
    if tarfile.is_tarfile(file_path):
        tmp_dir = tempfile.mkdtemp()
        destination = os.path.join(tmp_dir, 'repo')
        tar = tarfile.open(file_path, 'r:gz')
        tar.extractall(destination)
        tar.close()
        return destination


def overwrite_dir(source, destination='/opt/ice-repo/'):
    """
    Copy all files from _source_ to a temporary location (if not in a temporary
    location already) and then overwrite the contents of its destination so
    that the contents are as up to date as possible
    """
    # TODO: Need to define the destination of respository files, for example:
    # /opt/ice-repo

    # remove destination to ensure we get a fresh copy
    try:
        shutil.rmtree(destination)
    except OSError:
        os.mkdir(destination)

    # now copy the contents
    shutil.copytree(source, destination)

    # finally remove the source
    shutil.rmtree(source)


def default_repo_location():
    """
    Calculates the default repository location of the repository files, for
    example if this script runs alongside the sources it would get the absolute
    path for the ``sources`` directory relative to this script.
    """
    # TODO: Needs to know about the location (and names) of directories
    # packaged alongside this script

    # XXX: bad naming here. Maybe `detect_repo_location`
    pass


# =============================================================================
# Prompts
# =============================================================================


def prompt(question, _raw_input=None):
    input_prompt = _raw_input or raw_input
    prefix = '%s-->%s ' % (COLOR_SEQ % (30 + COLORS['DEBUG']), RESET_SEQ)
    prompt_format = '{prefix} {question}'.format(prefix=prefix, question=question)
    response = input_prompt(prompt_format)
    try:
        return strtobool(response)
    except ValueError:
        logger.error('That response was invalid, please try again')
        return prompt(question, _raw_input=input_prompt)


def strtobool(val):
    """
    Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values are
    'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if 'val' is
    anything else.

    .. note:: lifted from distutils.utils.strtobool
    """
    try:
        val = val.lower()
    except AttributeError:
        val = str(val).lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1', '', None):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError("invalid input value: %r" % (val,))


# =============================================================================
# Actions
# =============================================================================

def configure(tar_file):
    """
    Decompress a tar file for the current host so that it can serve as a repo
    server and we can then install Calamari and ceph-deploy.
    """
    distro = get_distro()
    decompressed_repo = extract_file(tar_file)
    overwrite_dir(decompressed_repo)

    # TODO: Allow custom destinations
    distro.pkg_manager.create_repo_file(
        gpg_url='/opt/ice/repo/release.asc',
        repo_url='/opt/ice/repo',
        codename=distro.codename,
    )


def install(package):
    """
    Perform a package installation (e.g. Calamari or ceph-deploy) in the
    current host, abstracted away from the underlying package manager.
    """


# =============================================================================
# Main
# =============================================================================


def main(argv=None):
    argv = argv or sys.argv
    # Console Logger
    terminal_log = logging.StreamHandler()
    terminal_log.setFormatter(color_format(verbose='-v' in argv))
    logger.addHandler(terminal_log)
    logger.setLevel(logging.DEBUG)


if __name__ == '__main__':
    sys.exit(main())
