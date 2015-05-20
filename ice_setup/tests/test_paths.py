import tempfile
import os
import shutil

import pytest

from ice_setup.ice import get_package_source, DirNotFound, VersionNotFound


@pytest.fixture
def pkg_path():
    pkg_path = tempfile.mkdtemp()

    def fin():
        shutil.rmtree(pkg_path)
    return pkg_path


class TestGetPackageSource(object):

    def test_unversioned_missing(self, pkg_path):
        with pytest.raises(DirNotFound):
            get_package_source(pkg_path, 'ceph')

    def test_unversioned_ok(self, pkg_path):
        os.mkdir(os.path.join(pkg_path, 'ceph'))
        path = get_package_source(pkg_path, 'ceph')
        assert path == os.path.join(pkg_path, 'ceph')

    def test_versioned_gets_thrown_away(self, pkg_path):
        os.makedirs(os.path.join(pkg_path, 'ceph/0.80.0'))
        path = get_package_source(pkg_path, 'ceph')
        assert path == os.path.join(pkg_path, 'ceph')
