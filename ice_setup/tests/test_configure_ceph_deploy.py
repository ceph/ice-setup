import __builtin__
from errno import EROFS
from os import mkdir
from os.path import isfile

import pytest

from ice_setup.ice import configure_ceph_deploy

class TestConfigureCephDeploy(object):

    @pytest.fixture
    def mock_ceph_deploy_dirs(self, tmpdir, monkeypatch):
        """ configure_ceph_deploy() writes two files: one to the current
            working directory, and one to $HOME. """

        # monkeypatch cwd
        monkeypatch.setattr('ice_setup.ice.CWD', str(tmpdir))

        # monkeypatch HOME
        monkeypatch.setenv('HOME', str(tmpdir.join('testuser')))
        mkdir(str(tmpdir.join('testuser')))

        return tmpdir


    def test_write_files(self, mock_ceph_deploy_dirs):
        """ Test the usual case of writing two cephdeploy.conf files. """
        configure_ceph_deploy(
            'master.example.com',
            'http://master.example.com/ceph-mon/',
            'http://master.example.com/release.asc',
            'http://master.example.com/ceph-osd/',
            'http://master.example.com/release.asc',
            use_gpg=True,
        )
        cwd_file  = mock_ceph_deploy_dirs.join('cephdeploy.conf')
        home_file = mock_ceph_deploy_dirs.join('testuser', '.cephdeploy.conf')
        assert isfile(str(cwd_file)) is True
        assert isfile(str(home_file)) is True


    def mock_open_ioerror(self, *args, **kwargs):
        """ Raises an EROFS IOError. Use this to mock the open() builtin. """
        raise IOError(EROFS, 'Read-only file system: %s' % args[0])


    def test_read_only_error(self, mock_ceph_deploy_dirs, monkeypatch):
        """ Test when open() raises an EROFS IOError """
        monkeypatch.setattr(__builtin__, 'open', self.mock_open_ioerror)

        # We should see a regular SystemExit here, not IOError.
        with pytest.raises(SystemExit):
            configure_ceph_deploy(
                'master.example.com',
                'http://master.example.com/ceph-mon/',
                'http://master.example.com/release.asc',
                'http://master.example.com/ceph-osd/',
                'http://master.example.com/release.asc',
                use_gpg=True,
            )
