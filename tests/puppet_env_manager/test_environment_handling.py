import unittest

from mock import Mock, patch, call
from subprocess import CalledProcessError

from puppet_env_manager.manager import EnvironmentManager


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(environment_dir='/etc/puppetlabs/code', validate=False)

    def test_calculate_environment_changes(self):
        """ Verifies the subsets of added, existing, and removed environments is calculated correctly
        """
        available = ('one', 'two', 'three', 'four')
        installed = ('three', 'four', 'five', 'six')

        added, existing, removed = self.manager.calculate_environment_changes(
            installed_set=set(installed),
            available_set=set(available))

        self.assertEqual(set(added), {'one', 'two'})
        self.assertEqual(set(existing), {'three', 'four'})
        self.assertEqual(set(removed), {'five', 'six'})

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.subprocess')
    def test_add_environment(self, mock_subprocess, mock_symlink):
        self.manager.new_workdir_path = '/bin/git-new-workdir'
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.return_value = '/etc/puppetlabs/code/test.123ABC'
        self.manager.install_puppet_modules = Mock()
        self.manager.lock_environment = Mock()
        self.manager.unlock_environment = Mock()

        self.manager.add_environment('test')

        self.manager.lock_environment.assert_called_once_with('test')
        mock_subprocess.check_output.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test.123ABC', 'test'
        ])
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test.123ABC', '/etc/puppetlabs/code/test')
        self.manager.install_puppet_modules.assert_called_once_with('test')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.logging')
    @patch('puppet_env_manager.manager.subprocess.check_output')
    def test_add_environment_error(self, mock_subprocess, mock_logger):
        self.manager.logger = mock_logger
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.return_value = '/etc/puppetlabs/code/test.123ABC'
        self.manager.install_puppet_modules = Mock()
        self.manager.lock_environment = Mock()
        self.manager.unlock_environment = Mock()
        mock_subprocess.side_effect = CalledProcessError(1, 'some command', 'some output')

        self.manager.new_workdir_path = '/bin/git-new-workdir'
        self.manager.add_environment('test')

        self.manager.lock_environment.assert_called_once_with('test')
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test.123ABC', 'test'
        ])
        mock_logger.error.assert_called_with(
            "Failed to add environment test, exited 1: some output"
        )
        self.assertEqual(self.manager.install_puppet_modules.call_count, 0, 'install_puppet_modules should not have been called')
        self.manager.unlock_environment.assert_called_once_with('test')

    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.path.islink')
    def test_remove_environment_dir(self, mock_islink, mock_rmtree):
        mock_islink.return_value = False

        self.manager.remove_environment('test')

        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test')

    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.unlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.path.islink')
    def test_remove_environment_link(self, mock_islink, mock_readlink, mock_unlink, mock_rmtree):
        mock_islink.return_value = True
        mock_readlink.return_value = '/etc/puppetlabs/code/test.123ABC'

        self.manager.remove_environment('test')

        mock_unlink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test.123ABC')

    def test_upstream_ref(self):
        self.manager._master_repo = Mock()
        self.manager._master_repo.refs = {'origin/test': 'mock_ref'}

        self.assertEqual(self.manager.upstream_ref('test'), 'mock_ref')

    def test_check_sync(self):
        repo = Mock()
        repo.head = Mock()
        repo.head.commit = '123abc'
        repo.is_dirty.return_value = False

        upstream_ref = Mock()
        upstream_ref.commit = '123abc'

        bad_ref = Mock()
        bad_ref.commit = "987fed"

        self.assertTrue(self.manager.check_sync(repo, upstream_ref))
        self.assertFalse(self.manager.check_sync(repo, bad_ref))

        repo.is_dirty.return_value = True
        self.assertFalse(self.manager.check_sync(repo, upstream_ref))


class TestUpdates(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(environment_dir='/etc/puppetlabs/code', validate=False)
        self.manager.logger = Mock()
        self.manager.lock_environment = Mock()
        self.manager.unlock_environment = Mock()
        self.mock_ref = Mock()
        self.mock_ref.commit.hexsha = '123abc'
        self.manager.upstream_ref = Mock(return_value=self.mock_ref)

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.Repo')
    def test_update_environment_in_sync(self, mock_repo):
        self.manager.noop = True
        self.manager.check_sync = Mock(return_value=True)

        self.manager.update_environment('test', force=False)

        self.manager.lock_environment.assert_called_once_with('test')
        self.manager.logger.info.assert_called_once_with('test already up to date at 123abc')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.rename')
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.subprocess.check_output')
    @patch('puppet_env_manager.manager.Repo')
    def test_update_environment_link(
            self, mock_repo, mock_subprocess, mock_islink, mock_readlink,
            mock_symlink, mock_rename, mock_rmtree):
        mock_repo.return_value = mock_repo
        mock_islink.return_value = True
        mock_readlink.return_value = '/etc/puppetlabs/code/test.old'
        self.manager.check_sync = Mock(return_value=False)
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.side_effect = [
            '/etc/puppetlabs/code/test.new',
            '/etc/puppetlabs/code/test.link',
        ]
        self.manager.new_workdir_path = '/bin/git-new-workdir'

        self.manager.update_environment('test', force=False)

        self.manager.lock_environment.assert_called_once_with('test')
        mock_repo.head.reset.assert_called_once_with(self.mock_ref.commit)
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test.new', 'test'
        ])
        self.manager.install_puppet_modules.assert_called_once_with('test')
        mock_islink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_readlink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test.new', '/etc/puppetlabs/code/test.link')
        mock_rename.assert_called_once_with('/etc/puppetlabs/code/test.link', '/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test.old')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.rename')
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.subprocess.check_output')
    @patch('puppet_env_manager.manager.Repo')
    def test_update_environment_dir(
            self, mock_repo, mock_subprocess, mock_islink, mock_readlink,
            mock_symlink, mock_rename, mock_rmtree):
        mock_repo.return_value = mock_repo
        mock_islink.return_value = False
        mock_readlink.return_value = '/etc/puppetlabs/code/test.old'
        self.manager.check_sync = Mock(return_value=False)
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.side_effect = [
            '/etc/puppetlabs/code/test.new',
            '/etc/puppetlabs/code/test.dir',
        ]
        self.manager.new_workdir_path = '/bin/git-new-workdir'

        self.manager.update_environment('test', force=False)

        self.manager.lock_environment.assert_called_once_with('test')
        mock_repo.head.reset.assert_called_once_with(self.mock_ref.commit)
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test.new', 'test'
        ])
        self.manager.install_puppet_modules.assert_called_once_with('test')
        mock_islink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_rename.assert_called_once_with('/etc/puppetlabs/code/test', '/etc/puppetlabs/code/test.dir')
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test.new', '/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test.dir')
        self.manager.unlock_environment.assert_called_once_with('test')

    @patch('puppet_env_manager.manager.os.path.isdir')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.listdir')
    def test_list_stale_environment_clones(self, mock_listdir, mock_readlink, mock_islink, mock_isdir):
        mock_listdir.return_value = [
            '.', '..', '.puppet.git', 'production', 'production.clone',
            'test', 'test.clone', 'test.123abc', 'live_test'
        ]
        mock_islink.side_effect = [
            True, False, True, False, False
        ]
        mock_readlink.side_effect = [
            '/etc/puppetlabs/code/production.clone',
            '/etc/puppetlabs/code/test.clone',
        ]
        mock_isdir.return_value = True

        stale_clones = self.manager.list_stale_environment_clones()
        self.assertListEqual(stale_clones, ['/etc/puppetlabs/code/test.123abc'])

        mock_listdir.assert_called_once_with('/etc/puppetlabs/code')
        self.assertEqual(mock_islink.call_count, 5)
        self.assertEqual(mock_isdir.call_count, 3)

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.shutil.rmtree')
    def test_cleanup_stale_environment_clones(self, mock_rmtree):
        self.manager.list_stale_environment_clones = Mock(return_value=[
            '/etc/puppetlabs/code/test.123abc', '/etc/puppetlabs/code/test.987fed'])

        self.manager.cleanup_stale_environment_clones()
        self.manager.lock_environment.assert_has_calls([call('test'), call('test')])
        mock_rmtree.assert_has_calls([
            call('/etc/puppetlabs/code/test.123abc'),
            call('/etc/puppetlabs/code/test.987fed'),
        ])
        self.manager.unlock_environment.assert_has_calls([call('test'), call('test')])
