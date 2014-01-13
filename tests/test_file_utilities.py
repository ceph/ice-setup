import ice_setup


class TestDestinationRepoPath(object):

    def test_path_ends_with_slash(self):
        repo_path = ice_setup.destination_repo_path('/foo/bar')
        assert repo_path == '/opt/ICE/ceph-repo/foo/bar'

    def test_actual_repo_path(self):
        repo_path = ice_setup.destination_repo_path('/tmp/ice/ceph-repo/')
        assert repo_path == '/opt/ICE/ceph-repo/'

    def test_path_with_release_file(self):
        repo_path = ice_setup.destination_repo_path('/tmp/ice/ceph-repo/release.asc')
        assert repo_path == '/opt/ICE/ceph-repo/release.asc'

