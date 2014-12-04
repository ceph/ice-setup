#!/usr/bin/env python

# Copyright 2013, Red Hat, Inc.
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
# Red Hat, Inc., and its affiliates disclaim any liability for any
# damages caused by use of this software or hardware in dangerous applications.

import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import urllib2
import urlparse

from functools import wraps
from textwrap import dedent

__version__ = '0.0.1'

help_header = """

8888888b.      888    888      .d8888b.
888   Y88b     888    888     d88P  Y88b
888    888     888    888     888    888
888   d88P     8888888888     888
8888888P"      888    888     888
888 T88b       888    888     888    888
888  T88b  d8b 888    888 d8b Y88b  d88P d8b
888   T88b Y8P 888    888 Y8P  "Y8888P"  Y8P

"""

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
# argument parser
# =============================================================================

# NOTE: lifted from http://pypi.python.org/pypi/tambo
# because we can't rely on argparse since it is not available on Python2.6
# and we support that version but we don't have a way to install dependencies

class BaseCommandline(dict):

    help          = ('-h', '--h', '--help', 'help')
    version       = ('--version', 'version')
    catch_help    = ''
    catch_version = ''

    def catches_help(self, force=True):
        if self.catch_help:
            if self.check_help or force:
                if [i for i in self.arguments if i in self.help]:
                    self.print_help()
            return False

    def print_help(self):
        self.writer.write(self.catch_help+'\n')
        self.exit()

    def print_version(self):
        self.writer.write(self.catch_version+'\n')
        self.exit()

    def catches_version(self, force=True):
        if self.catch_version:
            if self.check_version or force:
                if [i for i in self.arguments if i in self.version]:
                    self.print_version()
            return False


class Parse(BaseCommandline):

    def __init__(self, arguments, mapper=None, options=None,
                 check_help=True, check_version=True, writer=None):
        self.arguments     = arguments[1:]
        self.mapper        = mapper or {}
        self.options       = options or []
        self.check_help    = check_help
        self.check_version = check_version
        self._arg_count    = {}
        self._count_arg    = {}
        self.writer        = writer or sys.stdout
        self.exit          = sys.exit
        self.unkown_commands = []

    def _build(self):
        extra_args = [i for i in self.arguments]
        for opt in self.options:
            if isinstance(opt, (tuple, list)):
                value = self._single_value_from_list(opt)
                if value:
                    for v in opt:
                        self._remove_item(v, extra_args)
                        self._remove_item(value, extra_args)
                        self[v] = value
                continue
            value = self._get_value(opt)
            if value:
                self._remove_item(value, extra_args)
                self[opt] = self._get_value(opt)
            self._remove_item(opt, extra_args)
        self._remove_cli_helpers(extra_args)
        self.unkown_commands = extra_args

    def _remove_cli_helpers(self, _list):
        if self.catch_help:
            for arg in self.help:
                self._remove_item(arg, _list)
        if self.catch_version:
            for arg in self.version:
                self._remove_item(arg, _list)

    def _remove_item(self, item, _list):
        for index, i in enumerate(_list):
            if item == i:
                _list.pop(index)
        return _list

    def _single_value_from_list(self, _list):
        for value in _list:
            v = self._get_value(value)
            if v:
                return v

    def parse_args(self):
        # Help and Version:
        self.catches_help(force=False)
        self.catches_version(force=False)

        for count, argument in enumerate(self.arguments):
            self._arg_count[argument] = count
            self._count_arg[count]    = argument

        # construct the dictionary
        self._build()

    def _get_value(self, opt):
        count = self._arg_count.get(opt)
        if count == None:
            return None
        value = self._count_arg.get(count+1)

        return value

    def has(self, opt):
        if isinstance(opt, (tuple, list)):
            for i in opt:
                if i in self._arg_count.keys():
                    return True
            return False
        if opt in self._arg_count.keys():
            return True
        return False


class Transport(Parse):
    """
    This class inherits from the ``Parse`` object that provides the engine
    to parse arguments from the command line, and it extends the functionality
    to be able to dispatch on mapped objects to subcommands.

    :param arguments: Should be the *exact* list of arguments coming from ``sys.argv``
    :keyword mapper: A dictionary of mapped subcommands to classes
    """

    def dispatch(self):
        mapper_keys = self.mapper.keys()
        for arg in self.arguments:
            if arg in mapper_keys:
                instance = self.mapper.get(arg)(self.arguments)
                return instance.parse_args()
        self.parse_args()
        if self.unkown_commands:
            self.writer.write("Unknown command(s): %s\n" % ' '.join(self.unkown_commands))


    def subhelp(self):
        """
        This method will look at every value of every key in the mapper
        and will output any ``class.help`` possible to return it as a
        string that will be sent to stdout.
        """
        help_text = self._get_all_help_text()

        if help_text:
            return "Available subcommands:\n\n%s\n" % ''.join(help_text)
        return ''

    def _get_all_help_text(self):
        help_text_lines = []
        for key, value in self.mapper.items():
            try:
                help_text = value.help
            except AttributeError:
                continue
            help_text_lines.append("%-24s %s\n" % (key, help_text))
        return help_text_lines


# =============================================================================
# Exceptions
# =============================================================================

class RHCError(Exception):
    """Base RHC Setup exception"""
    pass


class NonZeroExit(RHCError):
    """subprocess commands that exit with non-zero status"""
    pass


class UnsupportedPlatform(RHCError):
    pass


class FileNotFound(RHCError):
    """
    Provide meaningful information when a given file is not found in the
    filesystem
    """

    def __init__(self, filepath):
        self.filepath = filepath
        Exception.__init__(self, self.__str__())

    def __str__(self):
        return 'could not find %s' % self.filepath


# =============================================================================
# Decorators
# =============================================================================

def catches(catch=None, handler=None, exit=True):
    """
    Very simple decorator that tries any of the exception(s) passed in as
    a single exception class or tuple (containing multiple ones) returning the
    exception message and optionally handling the problem if it raises with the
    handler if it is provided.

    So instead of doing something like this::

        def bar():
            try:
                some_call()
                print "Success!"
            except TypeError, exc:
                print "Error while handling some call: %s" % exc
                sys.exit(1)

    You would need to decorate it like this to have the same effect::

        @catches(TypeError)
        def bar():
            some_call()
            print "Success!"

    If multiple exceptions need to be caught they need to be provided as a
    tuple::

        @catches((TypeError, AttributeError))
        def bar():
            some_call()
            print "Success!"

    If adding a handler, it should accept a single argument, which would be the
    exception that was raised, it would look like::

        def my_handler(exc):
            print 'Handling exception %s' % str(exc)
            raise SystemExit

        @catches(KeyboardInterrupt, handler=my_handler)
        def bar():
            some_call()

    Note that the handler needs to raise its SystemExit if it wants to halt
    execution, otherwise the decorator would continue as a normal try/except
    block.

    """
    catch = catch or Exception

    def decorate(f):

        @wraps(f)
        def newfunc(*a, **kw):
            try:
                f(*a, **kw)
            except catch as e:
                if handler:
                    return handler(e)
                else:
                    logger.error(make_exception_message(e))
                    if exit:
                        sys.exit(1)
        return newfunc

    return decorate

#
# Decorator helpers
#


def make_exception_message(exc):
    """
    An exception is passed in and this function
    returns the proper string depending on the result
    so it is readable enough.
    """
    if str(exc):
        return '%s: %s' % (exc.__class__.__name__, exc)
    else:
        return '%s' % (exc.__class__.__name__)


# =============================================================================
# Templates
# =============================================================================

ceph_deploy_yum_template = """
[ceph_deploy]
name=ceph_deploy packages for $basearch
baseurl={repo_url}
enabled=1
gpgcheck=1
type=rpm-md
priority=1
gpgkey={gpg_url}
"""

calamari_yum_template = """
[calamari]
name=calamari packages for $basearch
baseurl={repo_url}
enabled=1
gpgcheck=1
type=rpm-md
priority=1
gpgkey={gpg_url}
"""

ceph_yum_template = """
[ceph]
name=Ceph
baseurl={repo_url}
gpgkey={gpg_url}
default=true
priority=1
proxy=_none_
"""

ceph_apt_template = """deb {repo_url} {codename} main\n"""

calamari_apt_template = """deb {repo_url} {codename} main\n"""

ceph_deploy_apt_template = """deb {repo_url} {codename} main\n"""


ceph_deploy_rc = """
# This file was automatically generated after rhc_setup.py was run. It provides
# the repository url and GPG information so that ceph-deploy can install the
# repositories in remote hosts.
#

# ceph-deploy subcommands

[ceph-deploy-calamari]
master = {master}


# Repositories

[calamari-minion]
name=Calamari
baseurl={minion_url}
gpgkey={minion_gpg_url}
enabled=1
priority=1
proxy=_none_

[ceph]
name=Ceph
baseurl={ceph_url}
gpgkey={ceph_gpg_url}
default=true
priority=1
proxy=_none_
"""


# template mappings

yum_templates = {
    'calamari-server': calamari_yum_template,
    'ceph-deploy': ceph_deploy_yum_template,
    'ceph': ceph_yum_template,
}

apt_templates = {
    'calamari-server': calamari_apt_template,
    'ceph-deploy': ceph_deploy_apt_template,
    'ceph': ceph_apt_template,
}




# =============================================================================
# Distributions
# =============================================================================


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


def append_item_or_list(list_, append):
    if isinstance(append, list):
        list_.extend(append)
    else:
        list_.append(append)


# XXX These probably do not need to be full of classmethods but can be
# instantiated when the distro detection happens

class Yum(object):

    @classmethod
    def create_repo_file(cls, template_name, repo_url, gpg_url, file_name=None, **kw):
        """set the contents of /etc/yum.repos.d/ice.repo"""
        etc_path = kw.pop('etc_path', '/etc/yum.repos.d')
        file_name = '%s.repo' % (file_name or 'ice')
        template = yum_templates[template_name]
        repo_file_path = os.path.join(etc_path, file_name)
        with open(repo_file_path, 'w') as repo_file:
            contents = template.format(
                gpg_url=gpg_url,
                repo_url=repo_url,
            )
            repo_file.write(contents)

    @classmethod
    def print_repo_file(cls, template_name, repo_url, gpg_url, file_name=None, **kw):
        """print repo file as it would be written to yum.repos.d"""
        template = yum_templates[template_name]
        logger.info('Contents of %s repo file:' % template_name)
        logger.info(template.format(
            gpg_url=gpg_url, repo_url=repo_url)
        )

    @classmethod
    def import_repo(cls, gpg_path):
        """
        import the gpg key so that the repo is fully validated
        """
        cmd = [
            'rpm',
            '--import',
            gpg_path,
        ]
        run(cmd)

    @classmethod
    def install(cls, package):
        cmd = [
            'yum',
            '-y',
            'install',
        ]
        append_item_or_list(cmd, package)
        run(cmd)

    @classmethod
    def update(cls):
        # stub
        pass

    @classmethod
    def enumerate_repo(cls, path):
        """find rpms in path and return their package names"""
        # make list of rpm files relative to path
        rpmlist = list()
        for dirpath, dirnames, filenames in os.walk(path):
            rpmlist += [name for name in filenames
                        if name.endswith('rpm')]
        cmd = [
            'rpm',
            '-q',
            '--queryformat=%{NAME} ',
            '-p',
        ]
        cmd.extend(rpmlist)
        # run command with cwd=path so rpm names are valid
        return run_get_stdout(cmd, cwd=path)


class Apt(object):

    @classmethod
    def create_repo_file(cls, template_name, repo_url, gpg_url, file_name=None, **kw):
        """add ceph deb repo to sources.list"""
        etc_path = kw.pop('etc_path', '/etc/apt/sources.list.d')
        file_name = '%s.list' % (file_name or 'ice')
        list_file_path = os.path.join(etc_path, file_name)
        template = apt_templates[template_name]
        with open(list_file_path, 'w') as list_file:
            list_file.write(template.format(
                repo_url=repo_url, codename=kw.pop('codename'))
            )

    @classmethod
    def print_repo_file(cls, template_name, repo_url, gpg_url, file_name=None, **kw):
        """print deb repo as it would be written to sources.list"""
        template = apt_templates[template_name]
        logger.info('Contents of %s deb sources.list file:' % template_name )
        logger.info(template.format(
            repo_url=repo_url, codename=kw.pop('codename'))
        )

    @classmethod
    def import_repo(cls, gpg_path):
        """
        import the gpg key so that the repo is fully validated
        """
        cmd = [
            'apt-key',
            'add',
            gpg_path,
        ]
        run(cmd)

    @classmethod
    def install(cls, package):
        cmd = [
            'sudo',
            'env',
            'DEBIAN_FRONTEND=noninteractive',
            'apt-get',
            'install',
            '--assume-yes',
        ]
        append_item_or_list(cmd, package)
        run(cmd)

    @classmethod
    def update(cls):
        cmd = [
            'apt-get',
            '-q',
            'update',
        ]
        run(cmd)

    @classmethod
    def enumerate_repo(cls, path):
        """find pkgs in path and return their package names"""
        # make list of debs
        deblist = list()
        for dirpath, dirnames, filenames in os.walk(path):
            deblist += [os.path.join(dirpath, name) for name in filenames
                        if name.endswith('deb')]
        # we could just chop at the first '_', but this is
        # arguably safer
        pkglist = list()
        for deb in deblist:
            cmd = ['dpkg-deb', '-f', deb, 'Package',]
            pkglist.append(run_get_stdout(cmd, quiet=True).rstrip())
        return ' '.join(pkglist)

class CentOS(object):
    pkg_manager = Yum()


class Debian(object):
    pkg_manager = Apt()


# Normalize casing for easier mapping
centos = CentOS
debian = Debian


# =============================================================================
# Subprocess
# =============================================================================


def run(cmd, **kw):
    logger.info('Running command: %s' % ' '.join(cmd))
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
                logger.debug(out.strip('\n'))
                sys.stdout.flush()

    returncode = process.wait()
    if returncode != 0:
        error_msg = "command returned non-zero exit status: %s" % returncode
        if stop_on_nonzero:
            raise NonZeroExit(error_msg)
        else:
            logger.warning(error_msg)


def run_get_stdout(cmd, **kw):
    """like run(), except return stdout rather than logging it"""
    stop_on_nonzero = kw.pop('stop_on_nonzero', True)
    quiet = kw.pop('quiet', False)

    if not quiet:
        logger.info('Running command: %s' % ' '.join(cmd))
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw
    )
    out, err = process.communicate()
    if err:
        logger.warning(err)

    if process.returncode != 0:
        error_msg = "command returned non-zero exit status: %s" % process.returncode
        if stop_on_nonzero:
            raise NonZeroExit(error_msg)
        else:
            logger.warning(error_msg)
    return out


def run_call(cmd, **kw):
    """
    a callable that will execute a subprocess without raising an exception if
    the exit status is non-zero.

    The ``logger`` argument is in the signature only for consistency in the
    API, it does nothing by default.
    """
    logger.info('Running command: %s' % ' '.join(cmd))
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


def get_fqdn(_socket=None):
    """
    Return what might be a valid FQDN and avoiding possible
    localhost names
    """
    sock = _socket or socket
    fqdn = sock.getfqdn()
    if fqdn.endswith('.local') or fqdn.startswith('localhost'):
        return None
    return fqdn


def _get_distro(distro, fallback=None):
    if not distro:
        return

    distro = _normalized_distro_name(distro)
    distributions = {
        'debian': debian,
        'ubuntu': debian,
        'centos': centos,
        'redhat': centos,
        }

    return distributions.get(distro) or _get_distro(fallback)


def _normalized_distro_name(distro):
    """
    Normalizes the distribution name so it is easier to operate on well knowns
    rather than whatever small differences distributions decide to add to them

    Even though we do not support Suse or Scientific, because we are just
    normalizing we don't mind leaving them here.
    """
    distro = distro.lower()
    if distro.startswith(('redhat', 'red hat')):
        return 'redhat'
    elif distro.startswith(('scientific', 'scientific linux')):
        return 'scientific'
    elif distro.startswith(('suse', 'opensuse')):
        return 'suse'
    elif distro.startswith('centos'):
        return 'centos'
    return distro


# =============================================================================
# File Utilities
# =============================================================================


def is_url(url_wannabe):
    """
    Make sure that a given argument is an actual, valid URL and that we can
    open it
    """
    if not url_wannabe:
        return False

    if os.path.exists(url_wannabe):
        return False
    try:
        url_fd = urllib2.urlopen(url_wannabe)
        url_fd.close()
        return True
    except (ValueError, AttributeError):
        return False


def download_file(url, filename=None, destination_dir='/opt/ice/tmp'):
    """
    Given a URL, download the contents to a pre-defined destination directory
    If the filename to save already exists it will get removed before starting
    the actual download.
    """
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)
    url_fd = urllib2.urlopen(urllib2.Request(url))
    filename_from_url = os.path.basename(urlparse.urlsplit(url_fd.url)[2])
    filename = filename or filename_from_url
    destination_path = os.path.join(destination_dir, filename)
    if os.path.isfile(destination_path):
        os.remove(destination_path)
    try:
        with open(destination_path, 'wb') as f:
            shutil.copyfileobj(url_fd, f)
    finally:
        url_fd.close()


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


def overwrite_dir(source, destination='/opt/ICE/ceph-repo/'):
    """
    Copy all files from _source_ to a temporary location (if not in a temporary
    location already) and then overwrite the contents of its destination so
    that the contents are as up to date as possible
    """
    if not os.path.exists(os.path.dirname(destination)):
        logger.info('creating destination path: %s' % destination)
        os.makedirs(destination, 0755)

    # remove destination to ensure we get a fresh copy
    try:
        shutil.rmtree(destination)
        logger.debug('ensuring destination is new')
        logger.debug('removed destination directory: %s' % destination)
    except OSError:
        pass

    # now copy the contents
    shutil.copytree(source, destination)
    logger.debug('copied contents from: %s to %s' % (source, destination))


def get_repo_path(repo_dir_name=None, traverse=False):
    """
    Calculates the repository location of the repository files, for example if
    this script runs alongside the sources it would get the absolute path for
    the ``ceph-repo`` or ``local-repo`` directories relative to this script.
    """
    repo_dir_name = repo_dir_name or 'ceph-repo'
    current_dir = os.path.abspath(os.path.dirname(__file__))
    repo_path = os.path.join(current_dir, repo_dir_name)
    if traverse:
        for root, dirs, files in os.walk(repo_path):
            # be blatant here so we break if the dir is not there
            repo_path = os.path.join(repo_path, dirs[0])
            break

    if not os.path.exists(repo_path):
        raise FileNotFound(repo_path)
    logger.debug('detected repository path: %s', repo_path)
    return repo_path


# =============================================================================
# Prompts
# =============================================================================


def prompt_bool(question, _raw_input=None):
    input_prompt = _raw_input or raw_input
    prefix = '%s-->%s ' % (COLOR_SEQ % (30 + COLORS['INFO']), RESET_SEQ)
    prompt_format = '{prefix}{question} '.format(prefix=prefix, question=question)
    response = input_prompt(prompt_format)
    try:
        return strtobool(response)
    except ValueError:
        logger.error('Valid true responses are: y, Y, 1, Enter')
        logger.error('Valid false responses are: n, N, 0')
        logger.error('That response was invalid, please try again')
        return prompt_bool(question, _raw_input=input_prompt)


def prompt_continue():
    if not prompt_bool('do you want to continue?'):
        raise SystemExit('exiting ice setup script')


def prompt(question, default=None, lowercase=False, _raw_input=None):
    """
    A more basic prompt which just needs some kind of user input, with the
    ability to pass in a default and will sanitize responses (e.g. striping
    whitespace).
    """
    input_prompt = _raw_input or raw_input
    prefix = '%s-->%s ' % (COLOR_SEQ % (30 + COLORS['DEBUG']), RESET_SEQ)
    if default:
        prompt_format = '{prefix}{question} [{default}] '.format(
            prefix=prefix,
            question=question,
            default=default
        )
    else:
        prompt_format = '{prefix}{question} '.format(prefix=prefix, question=question)
    response = input_prompt(prompt_format)
    if not response:  # e.g. user hit Enter
        return default
    else:
        response = str(response).strip()
        if lowercase:
            return response.lower()
        return response


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


class Configure(object):

    _help = dedent("""
    Configures the RHC node as a repository Host. Defaults to fetch a tar.gz
    from ceph.com that will have all the packages needed to create a
    repository.

    Commands:

      all         Both local and remote repo
      local       Local repo only, to install Calamari and/or ceph-deploy
      remote      Remote repo only, to be used for all remote node package
                  managers
    """)

    def __init__(self, argv):
        self.argv = argv

    def parse_args(self):
        options = ['all', 'local', 'remote']
        parser = Transport(self.argv, options=options)
        parser.catch_help = self._help
        parser.parse_args()

        sudo_check()

        if parser.has('all'):
            repo_path = parser.get('all')
            configure_local(repo_path=repo_path)
            configure_remotes(repo_path=repo_path)

        elif parser.has('local'):
            repo_path = parser.get('local')
            configure_local(repo_path=repo_path)

        elif parser.has('remote'):
            repo_path = parser.get('remote')
            configure_remotes(repo_path=repo_path)


def fqdn_with_protocol():
    """
    Prompt the user for the FQDN of the current server along with the
    protocol to be used so that we can configure the repositories.
    """
    fallback_fqdn = get_fqdn()
    logger.info('this host will be used to host packages')
    logger.info('and will act as a repository for other nodes')
    if fallback_fqdn is None:
        logger.warning('no FQDN could be detected for current host')
    fqdn = prompt('provide the FQDN for this host:', default=fallback_fqdn)

    # make sure we do have a FQDN of some sort, complain otherwise
    if not fqdn:
        logger.error('a FQDN is required and was not provided, please try again')
        return fqdn_with_protocol()

    protocol = prompt(
        'what protocol would this host use (http or https)?',
        default='http',
        lowercase=True,
    )

    return protocol, fqdn


def configure_remotes(
        repo_name,
        repo_path=None,
        destination_name=None,
        versioned=False):
    """
    Configure the current host so that Calamari can serve as a repo server for
    remote hosts. Some abstraction here allows us to configure any number of
    different repositories to be hosted by the Calamari app.

    :returns destination_name

    :param repo_name: the name of the repository, that will be used as the
    destination dir.

    :param repo_path: optionally specify the actual repository path to be moved

    :param destination_name: defaults to ``repo_name``, used to use a new
    destination name, e.g. 'ceph0.80' to help with versioning.

    :param versioned: if the repository is versioned (e.g. 'ceph-repo/0.80')
    then traverse one level in and use the first directory # XXX magic
    """
    destination_name = destination_name or repo_name
    repo_dest_prefix = '/opt/calamari/webapp/content'

    if not repo_path:  # fallback to our location
        # if we need to look for a versioned directory, tell get_repo_path to
        # traverse.
        repo_path = get_repo_path(repo_name, traverse=versioned)

    if versioned:
        # this means that we need to also grab the end part of the
        # repo_path, as that represents the version that should also
        # get used for the destination to avoid overwriting repos
        destination_name = os.path.join(
            destination_name, os.path.basename(repo_path)
        )

    # overwrite the repo with the new packages
    overwrite_dir(
        repo_path,
        destination=os.path.join(
            repo_dest_prefix,
            destination_name,
        )

    )

    return destination_name


def configure_ceph_deploy(master, minion_url, minion_gpg_url,
                          ceph_url, ceph_gpg_url):
    """
    Write the ceph-deploy conf to automagically tell ceph-deploy to use
    the right repositories and flags without making the user specify them
    """
    # ensure we write the config file in all these places because the $HOME
    # location might not be what the user expected to be
    configs = [
        os.path.join(os.getcwd(), 'cephdeploy.conf'),
        os.path.expanduser(u'~/.cephdeploy.conf'),
    ]
    sudoer_user = os.environ.get('SUDO_USER')
    if sudoer_user:
        sudoer_home = os.path.expanduser('~' + sudoer_user)
        configs.append(os.path.join(sudoer_home, '.cephdeploy.conf'))

    for cephdeploy_conf in configs:
        with open(cephdeploy_conf, 'w') as rc_file:
            contents = ceph_deploy_rc.format(
                master=master,
                minion_url=minion_url,
                minion_gpg_url=minion_gpg_url,
                ceph_url=ceph_url,
                ceph_gpg_url=ceph_gpg_url,
            )

            rc_file.write(contents)


def configure_local(name, repo_path=None):
    """
    Configure the current host so that it can serve as a *local* repo server
    and we can then install Calamari and ceph-deploy.

    :param name: The name of the repository to be configured, e.g. calamari-server
                 or ceph-deploy
    """
    repo_dest_prefix = '/opt/ICE'
    repo_dest_dir = os.path.join(repo_dest_prefix, name)

    if not repo_path:  # fallback to our location
        repo_path = get_repo_path(repo_dir_name=name)

    gpg_path = os.path.join(repo_dest_dir, 'release.asc')
    gpg_url_path = 'file://%s' % gpg_path

    repo_url_path = 'file://%s' % os.path.join(
        repo_dest_prefix,
        name,
    )

    # overwrite the repo with the new packages
    overwrite_dir(
        repo_path,
        destination=os.path.join(
            repo_dest_prefix,
            name,
        )
    )

    distro = get_distro()
    distro.pkg_manager.create_repo_file(
        name,
        repo_url_path,
        gpg_url_path,
        file_name=name,
        codename=distro.codename,
    )

    distro.pkg_manager.import_repo(
        gpg_path,
    )

    # call update on the package manager
    distro.pkg_manager.update()
    logger.info('this host now has a local repository for ceph-deploy, and Calamari')
    logger.info('you can install those packages with your package manager')


def install_calamari(distro=None):
    """ Installs the Calamari web application """
    distro = distro or get_distro()
    logger.debug('installing Calamari...')
    pkgs = distro.pkg_manager.enumerate_repo('/opt/ICE/calamari-server').split()
    distro.pkg_manager.install(pkgs)


def install_ceph_deploy(distro=None):
    """ Installs ceph-deploy """
    distro = distro or get_distro()
    logger.debug('installing ceph-deploy...')
    distro.pkg_manager.install('ceph-deploy')


def default():
    """
    This action is the default entry point for a generic RHC setup. It goes
    through all the common questions and prompts for a user and initiates the
    configuration and setup. It does not offer granular support for given
    actions, e.g. "just install Calamari".
    """
    interactive_help()
    configure_steps = [
        '1. Configure the RHC Node (current host) as a repository Host',
        '2. Install Calamari web application on the RHC Node (current host)',
        '3. Install ceph-deploy on the RHC Node (current host)',
        '4. Configure host as a ceph and calamari minion repository for remote hosts',
    ]

    logger.info('this script will setup Calamari, package repo, and ceph-deploy')
    logger.info('with the following steps:')
    for step in configure_steps:
        logger.info(step)

    # step one, we can have lots of fun
    # configure local repos for calamari and ceph-deploy
    logger.info('')
    logger.info('{markup} Step 1: Calamari & ceph-deploy repo setup {markup}'.format(markup='===='))
    logger.info('')
    configure_local('calamari-server')
    configure_local('ceph-deploy')

    # step two, there's so much we can do
    # install calamari
    logger.info('')
    logger.info('{markup} Step 2: Calamari installation {markup}'.format(markup='===='))
    logger.info('')
    install_calamari()

    # step three, it's just you for me
    # install ceph-deploy
    logger.info('')
    logger.info('{markup} Step 3: ceph-deploy installation {markup}'.format(markup='===='))
    logger.info('')
    install_ceph_deploy()

    # confirm the right protocol and fqdn for this host
    protocol, fqdn = fqdn_with_protocol()

    # step four, I can give you more
    # configure current host to serve ceph packages
    #for step, repo in enumerate(['ceph-repo', 'minion-repo'], 4):
    logger.info('')
    logger.info('\
        {markup} \
        Step 4: ceph repository setup \
        {markup}'.format(markup='===='))
    logger.info('')
    # configure the repo, tell it we want to keep versions around
    ceph_destination_name = configure_remotes('ceph', versioned=True)

    # step five, don't you know that the time has arrived
    # configure current host to serve minion packages
    logger.info('')
    logger.info('\
        {markup} \
        Step 5: minion repository setup \
        {markup}'.format(markup='===='))
    logger.info('')
    configure_remotes('calamari-minions')

    # create the proper URLs for the repos
    minion_url = '%s://%s/static/calamari-minions' % (protocol, fqdn)
    ceph_url = '%s://%s/static/%s' % (protocol, fqdn, ceph_destination_name)
    ceph_gpg_url = '%s://%s/static/%s/release.asc' % (
        protocol,
        fqdn,
        ceph_destination_name
    )
    minion_gpg_url = '%s://%s/static/calamari-minions/release.asc' % (
        protocol,
        fqdn
    )

    # write the ceph-deploy configuration file with the new repo info
    configure_ceph_deploy(
        fqdn,
        minion_url,
        minion_gpg_url,
        ceph_url,
        ceph_gpg_url,
    )

    # Print the output of what would the repo file look for remotes
    distro = get_distro()
    distro.pkg_manager.print_repo_file(
        'ceph',
        repo_url=ceph_url,
        gpg_url=ceph_gpg_url,
        codename=distro.codename,
    )

    logger.info('Setup has completed.')
    logger.info('If installing Calamari for the first time:')
    logger.info('')
    logger.info('  Initialize Calamari (as root) by running:')
    logger.info('')
    logger.info('    calamari-ctl initialize')
    logger.info('')

    logger.info('To install the repo files on remote nodes with ceph-deploy, run:')
    logger.info('    ceph-deploy install --repo {HOSTS}')
    logger.info('')
    logger.warning('If upgrading, `ceph-deploy install {HOSTS}` will also upgrade ceph on remote nodes')
    logger.info('')
    logger.info('To install ceph on remote nodes with ceph-deploy, run:')
    logger.info('    ceph-deploy install {HOSTS}')
    logger.info('')


def interactive_help(mode='interactive mode'):
    """
    Display a re-usable set of instructions before entering a given action,
    like setting up the repository for remote nodes, that will provide the same
    information when the interactive mode is running.
    """
    logger.info('')
    logger.info('{markup} {mode} {markup}'.format(markup='====', mode=mode))
    logger.info('')
    logger.info('follow the prompts to complete the %s', mode)
    logger.info('if specific actions are required (e.g. just install Calamari)')
    logger.info('cancel this script with Ctrl-C, and see the help menu for details')
    logger.info('default values are presented in brackets')
    logger.info('press Enter to accept a default value, if one is provided')
    prompt_continue()


# =============================================================================
# Main
# =============================================================================

command_map = {
    'configure': Configure,
}


def ice_help():
    version = '  Version: %s' % __version__
    commands = """

    Subcommands:

      configure         Configuration of the RHC node
    """
    return '%s\n%s\n%s\n%s' % (
        help_header,
        '  Red Hat Ceph Setup',
        version,
        dedent(commands),
    )


def sudo_check():
    """
    Make sure that the executing user is either 'root' or
    is making use of `sudo`.
    """
    if os.getuid() != 0:
        msg = 'This script needs to be executed with sudo'
        raise RHCError(msg)


@catches(RHCError)
def main(argv=None):
    options = [['-v', '--verbose']]
    argv = argv or sys.argv
    parser = Transport(argv, mapper=command_map, options=options)
    parser.parse_args()

    # Console Logger
    terminal_log = logging.StreamHandler()
    terminal_log.setFormatter(
        color_format(
            verbose=parser.has(('-v', '--verbose'))
        )
    )
    logger.addHandler(terminal_log)
    logger.setLevel(logging.DEBUG)

    # parse first with no help; set defaults later
    parser.catch_version = __version__
    parser.catch_help = ice_help()
    parser.dispatch()

    # if dispatch did not catch anything now, parse help
    parser.catches_help()
    parser.catches_version()

    # when no arguments are passed in, just use our default routine
    if not parser.arguments:
        sudo_check()
        default()


if __name__ == '__main__':
    # This try/except dance *just* for KeyboardInterrupt is horrible but there
    # is no other way around it if not caught explicitly as opposed to using
    # the `@catches` decorator. See: http://bugs.python.org/issue1687125
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit('')
