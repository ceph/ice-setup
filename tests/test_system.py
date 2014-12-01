from rhc_setup import get_fqdn


class FakeSocket(object):
    pass


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
