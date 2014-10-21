import os
import tempfile
from pytest import raises
import pytest
from textwrap import dedent
from ice_setup import get_fqdn, infer_ceph_repo, ICEError, FileNotFound


class FakeSocket(object):
    pass


@pytest.fixture
def cephdeploy_conf():
    path = tempfile.mkstemp()

    def fin():
        os.remove(path)

    return path[-1]


class TestGetFQDN(object):

    def setup(self):
        self.sock = FakeSocket()

    def test_dot_local_fqdn(self):
        self.sock.getfqdn = lambda: 'alfredo.local'
        assert get_fqdn(_socket=self.sock) is None

    def test_localhost(self):
        self.sock.getfqdn = lambda: 'localhost'
        assert get_fqdn(_socket=self.sock) is None

    def test_valid_fqdn(self):
        self.sock.getfqdn = lambda: 'zombo.com'
        assert get_fqdn(_socket=self.sock) == 'zombo.com'


class TestInferCephRepo(object):

    def test_does_not_find_cephdeployconf(self):
        with raises(FileNotFound):
            infer_ceph_repo(_configs=[''])

    def test_does_not_find_a_ceph_repo_section(self, cephdeploy_conf):
        with raises(ICEError):
            infer_ceph_repo(_configs=[cephdeploy_conf])

    def test_does_find_a_ceph_repo_section(self, cephdeploy_conf):
        print cephdeploy_conf

        with open(cephdeploy_conf, 'w') as f:
            f.write(dedent("""
            [ceph]
            baseurl=http://fqdn/static/ceph/0.80
            """))
        result = infer_ceph_repo(_configs=[cephdeploy_conf])
        assert result == '/opt/calamari/webapp/content/ceph/0.80'

    def test_deals_with_non_trailing_slashes(self, cephdeploy_conf):
        print cephdeploy_conf

        with open(cephdeploy_conf, 'w') as f:
            f.write(dedent("""
            [ceph]
            baseurl=http://fqdn/static/ceph/0.80/
            """))
        result = infer_ceph_repo(_configs=[cephdeploy_conf])
        assert result == '/opt/calamari/webapp/content/ceph/0.80'
