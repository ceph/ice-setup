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
import urllib2
import urlparse
from textwrap import dedent

__version__ = '0.0.1'

help_heather = """

8888888      .d8888b.      8888888888
  888       d88P  Y88b     888
  888       888    888     888
  888       888            8888888
  888       888            888
  888       888    888     888
  888   d8b Y88b  d88P d8b 888        d8b
8888888 Y8P  "Y8888P"  Y8P 8888888888 Y8P

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


def log_header():
    """
    Simple helper to get the header and the version logged at
    debug level to the console
    """
    for line in help_heather.split('\n'):
        logger.debug(line)
    logger.debug('      Inktank Ceph Enterprise Setup')
    logger.debug('      Version: %s', __version__)
    logger.debug('')


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

class ICEError(Exception):
    """Base ICE Setup exception"""
    pass


class NonZeroExit(ICEError):
    """subprocess commands that exit with non-zero status"""
    pass


class UnsupportedPlatform(ICEError):
    pass


class FileNotFound(ICEError):
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


# XXX These probably do not need to be full of classmethods but can be
# instantiated when the distro detection happens

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
            '-q',
            'install',
        ]
        cmd.append(package)
        run(cmd)

    @classmethod
    def update(cls):
        # stub
        pass


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
            '-q',
            'install',
            '--assume-yes',
        ]
        cmd.append(package)
        run(cmd)

    @classmethod
    def update(cls):
        cmd = [
            'apt-get',
            '-q',
            'update',
        ]
        run(cmd)


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
        os.makedirs(destination, 0755)

    # remove destination to ensure we get a fresh copy
    try:
        shutil.rmtree(destination)
    except OSError:
        os.mkdir(destination)

    # now copy the contents
    shutil.copytree(source, destination)

    # finally remove the source
    shutil.rmtree(source)


def get_repo_path():
    """
    Calculates the repository location of the repository files, for
    example if this script runs alongside the sources it would get the absolute
    path for the ``sources`` directory relative to this script.
    """
    current_dir = os.path.abspath(os.path.dirname(__file__))
    repo_path = os.path.join(current_dir, 'ceph-repo')
    if not os.path.exists(repo_path):
        raise FileNotFound(repo_path)
    return repo_path


def destination_repo_path(path, sep='ceph-repo', prefix='/opt/ICE/ceph-repo'):
    """
    Creates the final destination absolute path for the ceph repo files and the
    gpg key
    """
    end_part = path.split(sep)[-1]
    if end_part.startswith('/'):  # remove initial slash
        end_part = end_part[1:]
    return os.path.join(prefix, end_part)

# =============================================================================
# Prompts
# =============================================================================


def prompt(question, _raw_input=None):
    input_prompt = _raw_input or raw_input
    prefix = '%s-->%s ' % (COLOR_SEQ % (30 + COLORS['DEBUG']), RESET_SEQ)
    prompt_format = '{prefix}{question} '.format(prefix=prefix, question=question)
    response = input_prompt(prompt_format)
    try:
        return strtobool(response)
    except ValueError:
        logger.error('Valid true responses are: y, Y, 1, Enter')
        logger.error('Valid false responses are: n, N, 0')
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


class Configure(object):

    _help = dedent("""
    Configures the ICE node as a repository Host. Defaults to fetch a tar.gz
    from ceph.com that will have all the packages needed to create a
    repository.

    Optional arguments:

      [tar.gz]    A tar.gz file to set the repository
    """)

    def __init__(self, argv):
        self.argv = argv

    def parse_args(self):
        parser = Transport(self.argv)
        parser.catch_help = self._help
        parser.parse_args()
        repo_dest_prefix = '/opt/ICE'

        repo_path = parser.arguments[0] if parser.arguments else None
        if not repo_path:  # fallback to our location
            repo_path = get_repo_path()

        # XXX need to make sure this is correct
        gpg_path = destination_repo_path(
            os.path.join(repo_path, 'release.asc')
        )
        gpg_url_path = 'file://%s' % gpg_path
        repo_url_path = 'file://%s' % destination_repo_path(repo_path)

        # overwrite the repo with the new packages
        overwrite_dir(repo_path)

        distro = get_distro()
        distro.pkg_manager.create_repo_file(
            gpg_url_path,
            repo_url_path,
        )

        distro.pkg_manager.import_repo(
            gpg_path,
        )

        # call update on the package manager
        distro.pkg_manager.update()

        # TODO: Move this logic to configure_ice
        raise SystemExit(configure_ice())


class Install(object):
    pass


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
    distro = get_distro()
    distro.pkg_manager.install(package)


def configure_ice():
    """
    """
    logger.debug('configuring the ICE node as a repository host')


def install_calamari():
    """ Installs the Calamari web application """
    logger.debug('installing Calamari')


def install_ceph_deploy():
    """ Installs ceph-deploy """
    logger.debug('installing ceph-deploy')


def default():
    """
    This action is the default entry point for a generic ICE setup. It goes
    through all the common questions and prompts for a user and initiates the
    configuration and setup. It does not offer granular support for given
    actions, e.g. "just install Calamari".
    """
    configure_steps = [
        '1. Configure the ICE Node (current host) as a repository Host',
        '2. Install Calamari web application on the ICE Node (current host)',
        '3. Install ceph-deploy on the ICE Node (current host)',
        '4. Open the Calamari web interface',
    ]
    logger.debug('This interactive script will help you setup Calamari, package repo, and ceph-deploy')
    logger.debug('with the following steps:')
    for step in configure_steps:
        logger.debug(step)
    logger.debug('If specific actions are required (e.g. just install Calamari) cancel, and call `--help`')

    if prompt('Do you want to continue?'):
        logger.debug('Configure ICE Node')


# =============================================================================
# Main
# =============================================================================

command_map = {
    'install': Install,
    'configure': Configure,
}


def ice_help():
    version = '  Version: %s' % __version__
    commands = """

    Subcommands:

      install           Installation of Calamari or ceph-deploy
      configure         Configuration of the ICE node
      open              Open the Calamari web interface
    """
    return '%s\n%s\n%s\n%s' % (
        help_heather,
        '  Inktank Ceph Enterprise Setup',
        version,
        dedent(commands),
    )


def main(argv=None):
    # TODO:
    # * add the user prompts for first time runs
    # * implement hybrid behavior via commands and/or prompts
    #   ice_setup.py install calamari
    # * check if executing user is super user (or root), fail otherwise
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

    # parse first with no help set defaults later
    parser.catch_version = __version__
    parser.catch_help = ice_help()
    parser.dispatch()

    # if dispatch did not catch anything now parse help
    parser.catches_help()
    parser.catches_version()

    # XXX check for no arguments so we can use default, otherwise we
    # would need to exit() on all the commands from above
    default()


if __name__ == '__main__':
    sys.exit(main())
