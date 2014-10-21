import os
import pytest
import shutil
import tempfile
from ice_setup import Yum, Apt


@pytest.fixture
def etc_path():
    dir_path = tempfile.mkdtemp()

    def fin():
        shutil.rmtree(dir_path)
    return dir_path


class TestYum(object):

    def test_creates_default_file(self, etc_path):
        Yum.create_repo_file('ceph', 'repo_url', 'gpg_url', etc_path=etc_path)
        assert os.path.isfile(os.path.join(etc_path, 'ice.repo'))

    def test_gpg_url_default_file(self, etc_path):
        Yum.create_repo_file('ceph', 'repo_url', 'gpg_url', etc_path=etc_path)
        repo_file_path = os.path.join(etc_path, 'ice.repo')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert 'gpg_url' in contents

    def test_repo_url_default_file(self, etc_path):
        Yum.create_repo_file('ceph', '/opt/ICE/repo', 'gpg_url', etc_path=etc_path)
        repo_file_path = os.path.join(etc_path, 'ice.repo')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert '/opt/ICE/repo' in contents

    def test_creates_custom_file(self, etc_path):
        Yum.create_repo_file('ceph', 'repo_url', 'gpg_url', file_name='foo', etc_path=etc_path)
        assert os.path.isfile(os.path.join(etc_path, 'foo.repo'))

    def test_gpg_url_custom_file(self, etc_path):
        Yum.create_repo_file('ceph', 'repo_url', 'gpg_url', file_name='foo', etc_path=etc_path)
        repo_file_path = os.path.join(etc_path, 'foo.repo')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert 'gpg_url' in contents

    def test_repo_url_custom_file(self, etc_path):
        Yum.create_repo_file('ceph', '/opt/ICE/repo', 'gpg_url', file_name='foo',  etc_path=etc_path)
        repo_file_path = os.path.join(etc_path, 'foo.repo')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert '/opt/ICE/repo' in contents


class TestApt(object):

    def test_creates_default_file(self, etc_path):
        Apt.create_repo_file('ceph', 'repo_url', 'gpg_url', etc_path=etc_path, codename='saucy')
        assert os.path.isfile(os.path.join(etc_path, 'ice.list'))

    def test_gpg_url_default_file(self, etc_path):
        Apt.create_repo_file('ceph', 'repo_url', 'gpg_url', etc_path=etc_path, codename='saucy')
        repo_file_path = os.path.join(etc_path, 'ice.list')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert 'repo_url' in contents

    def test_repo_url_default_file(self, etc_path):
        Apt.create_repo_file('ceph', '/opt/ICE/repo', 'gpg_url', etc_path=etc_path, codename='saucy')
        repo_file_path = os.path.join(etc_path, 'ice.list')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert '/opt/ICE/repo' in contents

    def test_creates_custom_file(self, etc_path):
        Apt.create_repo_file('ceph', 'repo_url', 'gpg_url', file_name='foo', etc_path=etc_path, codename='saucy')
        assert os.path.isfile(os.path.join(etc_path, 'foo.list'))

    def test_gpg_url_custom_file(self, etc_path):
        Apt.create_repo_file('ceph', 'repo_url', 'gpg_url', file_name='foo', etc_path=etc_path, codename='saucy')
        repo_file_path = os.path.join(etc_path, 'foo.list')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert 'repo_url' in contents

    def test_repo_url_custom_file(self, etc_path):
        Apt.create_repo_file('ceph', '/opt/ICE/repo', 'gpg_url', file_name='foo',  etc_path=etc_path, codename='saucy')
        repo_file_path = os.path.join(etc_path, 'foo.list')
        with open(repo_file_path) as contents:
            contents = contents.read()
        assert '/opt/ICE/repo' in contents

