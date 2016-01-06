import pytest
from os.path import isfile
from ice_setup.ice import pin_local_repos, CentOS, Debian

class TestPinLocalRepos(object):

    @pytest.mark.parametrize('distro,expected', [
        (CentOS, False),
        (Debian, True),
    ])
    def test_distro_writes_pref_file(self, distro, expected, tmpdir):
        path = str(tmpdir.join('rhcs.pref'))
        pin_local_repos(path=path, distro=distro)
        # RPM distros should not write the apt prefs file
        assert isfile(path) is expected
