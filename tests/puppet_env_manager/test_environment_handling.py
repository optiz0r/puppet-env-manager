import subprocess
import unittest

from mock import Mock, patch, call, PropertyMock

from puppet_env_manager.manager import EnvironmentManager


class TestEnvironmentHandling(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(environment_dir='/etc/puppetlabs/code', validate=False)

    def test_prune_stale_refs(self):
        self.manager._master_repo = Mock()
        stale_ref = Mock()
        stale_ref.name = 'origin/test'
        stale_ref.remote_head = 'test'
        remote = Mock()
        type(remote).stale_refs = PropertyMock(return_value=[stale_ref])

        self.manager.prune_stale_refs(remote)

        stale_ref.delete.assert_called_once_with(self.manager._master_repo, stale_ref)
        self.assertListEqual(self.manager._pruned_environments, ['test'])

    @patch('puppet_env_manager.manager.os.listdir')
    def test_list_installed_environments(self, mock_listdir):
        mock_listdir.return_value = [
            '.', '..', '.puppet.git', '.production.lock', 'production', 'production__clone', 'test'
        ]
        expected = ['production', 'test']

        installed = self.manager.list_installed_environments()
        self.assertListEqual(expected, installed)

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

    def test_calculate_environment_changes_with_pruned(self):
        """ Verifies the subsets of added, existing, and removed environments is calculated correctly
        """
        available = ('one', 'two', 'three')
        self.manager._pruned_environments = ['four']
        installed = ('three', 'four', 'five', 'six')

        added, existing, removed = self.manager.calculate_environment_changes(
            installed_set=set(installed),
            available_set=set(available))

        self.assertEqual(set(added), {'one', 'two'})
        self.assertEqual(set(existing), {'three'})
        self.assertEqual(set(removed), {'four', 'five', 'six'})

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.subprocess.Popen')
    def test_add_environment(self, mock_subprocess, mock_symlink):
        mock_subprocess.return_value = mock_subprocess
        mock_subprocess.communicate.return_value = ('', '')
        mock_subprocess.poll.return_value = 0
        self.manager.new_workdir_path = '/bin/git-new-workdir'
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.return_value = '/etc/puppetlabs/code/test__123ABC'
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_resource_type_cache = Mock()
        self.manager.lock_environment = Mock()
        self.manager.unlock_environment = Mock()

        self.manager.add_environment('test')

        self.manager.lock_environment.assert_called_once_with('test')
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test__123ABC', 'test'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test__123ABC', '/etc/puppetlabs/code/test')
        self.manager.install_puppet_modules.assert_called_once_with('/etc/puppetlabs/code/test')
        self.manager.generate_resource_type_cache.assert_called_once_with('/etc/puppetlabs/code/test')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.logging')
    @patch('puppet_env_manager.manager.subprocess.Popen')
    def test_add_environment_error(self, mock_subprocess, mock_logger):
        mock_subprocess.return_value = mock_subprocess
        mock_subprocess.communicate.return_value = ('some output', 'some error')
        mock_subprocess.poll.return_value = 1
        self.manager.logger = mock_logger
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.return_value = '/etc/puppetlabs/code/test__123ABC'
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_resource_type_cache = Mock()
        self.manager.lock_environment = Mock()
        self.manager.unlock_environment = Mock()

        self.manager.new_workdir_path = '/bin/git-new-workdir'
        self.manager.add_environment('test')

        self.manager.lock_environment.assert_called_once_with('test')
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test__123ABC', 'test'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_logger.error.assert_called_with(
            "Failed to add environment test, exited 1: some output, some error"
        )
        self.assertEqual(self.manager.install_puppet_modules.call_count, 0,
                         'install_puppet_modules should not have been called')
        self.assertEqual(self.manager.generate_resource_type_cache.call_count, 0,
                         'generate_resource_type_cache should not have been called')
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
        mock_readlink.return_value = '/etc/puppetlabs/code/test__123ABC'

        self.manager.remove_environment('test')

        mock_unlink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test__123ABC')

    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.unlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.path.islink')
    def test_remove_environment_relative_link(self, mock_islink, mock_readlink, mock_unlink, mock_rmtree):
        mock_islink.return_value = True
        mock_readlink.return_value = 'test__123ABC'

        self.manager.remove_environment('test')

        mock_unlink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test__123ABC')

    @patch('puppet_env_manager.manager.subprocess.Popen')
    def test_generate_resource_type_cache(self, mock_subprocess):
        mock_process = Mock()
        mock_process.communicate.return_value = ('some output', 'some error')
        mock_process.poll.return_value = 0
        mock_subprocess.return_value = mock_process
        self.manager.identify_environment_name_from_path = Mock(return_value='test__clone')
        self.manager.logger = Mock()

        self.manager.generate_resource_type_cache('/etc/puppetlabs/code/test__clone', force=False)

        mock_subprocess.assert_called_once_with(
            [
                'puppet', 'generate', 'types', '--environmentpath', '/etc/puppetlabs/code',
                '--environment', 'test__clone'
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        mock_process.communicate.assert_called_once_with()
        mock_process.poll.assert_called_once_with()
        self.assertEqual(self.manager.logger.error.call_count, 0, 'No errors should be logged')

    @patch('puppet_env_manager.manager.subprocess.Popen')
    def test_generate_resource_type_cache_forced(self, mock_subprocess):
        mock_process = Mock()
        mock_process.communicate.return_value = ('some output', 'some error')
        mock_process.poll.return_value = 0
        mock_subprocess.return_value = mock_process
        self.manager.identify_environment_name_from_path = Mock(return_value='test__clone')
        self.manager.logger = Mock()

        self.manager.generate_resource_type_cache('/etc/puppetlabs/code/test__clone', force=True)

        mock_subprocess.assert_called_once_with(
            [
                'puppet', 'generate', 'types', '--environmentpath', '/etc/puppetlabs/code',
                '--environment', 'test__clone', '--force'
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        mock_process.communicate.assert_called_once_with()
        mock_process.poll.assert_called_once_with()
        self.assertEqual(self.manager.logger.error.call_count, 0, 'No errors should be logged')

    @patch('puppet_env_manager.manager.subprocess.Popen')
    def test_generate_resource_type_cache_failed(self, mock_subprocess):
        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = ('some output', 'some error')
        mock_subprocess.return_value = mock_process
        self.manager.identify_environment_name_from_path = Mock(return_value='test__clone')
        self.manager.logger = Mock()

        self.manager.generate_resource_type_cache('/etc/puppetlabs/code/test__clone', force=False)

        mock_subprocess.assert_called_once_with(
            [
                'puppet', 'generate', 'types', '--environmentpath', '/etc/puppetlabs/code',
                '--environment', 'test__clone'
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        mock_process.communicate.assert_called_once_with()
        mock_process.poll.assert_called_once_with()
        self.manager.logger.error.assert_has_calls([
            call("Failed to generate resource type cache for test__clone, exited 1: some output, some error")
        ])

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
    @patch('puppet_env_manager.manager.shutil.copytree')
    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.rename')
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.listdir')
    @patch('puppet_env_manager.manager.os.path.exists')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.subprocess.Popen')
    @patch('puppet_env_manager.manager.Repo')
    def test_update_environment_link(
            self, mock_repo, mock_subprocess, mock_islink, mock_exists, mock_listdir, mock_readlink,
            mock_symlink, mock_rename, mock_rmtree, mock_copytree):
        mock_subprocess.return_value = mock_subprocess
        mock_subprocess.communicate.return_value = ('', '')
        mock_subprocess.poll.return_value = 0
        mock_repo.return_value = mock_repo
        mock_exists.return_value = True
        mock_islink.return_value = True
        mock_readlink.return_value = '/etc/puppetlabs/code/test__old'
        mock_listdir.return_value = ['one', 'two']
        self.manager.check_sync = Mock(return_value=False)
        self.manager.has_puppetfile_changed = Mock(return_value=True)
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_resource_type_cache = Mock()
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.side_effect = [
            '/etc/puppetlabs/code/test__new',
            '/etc/puppetlabs/code/test__link',
        ]
        self.manager.new_workdir_path = '/bin/git-new-workdir'

        self.manager.update_environment('test', force=False)

        self.manager.lock_environment.assert_called_once_with('test')
        mock_repo.head.reset.assert_called_once_with(self.mock_ref.commit)
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test__new', 'test'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_subprocess.communicate.assert_called_once_with()
        mock_subprocess.poll.assert_called_once_with()
        mock_copytree.assert_has_calls([
            call('/etc/puppetlabs/code/test/thirdparty/one', '/etc/puppetlabs/code/test__new/thirdparty/one', symlinks=True),
            call('/etc/puppetlabs/code/test/thirdparty/two', '/etc/puppetlabs/code/test__new/thirdparty/two', symlinks=True)
        ])
        self.manager.install_puppet_modules.assert_called_once_with('/etc/puppetlabs/code/test__new')
        self.manager.generate_resource_type_cache.assert_called_once_with('/etc/puppetlabs/code/test__new', force=False)
        mock_islink.assert_has_calls([
            call('/etc/puppetlabs/code/test'), call('/etc/puppetlabs/code/test')
        ])
        mock_readlink.assert_called_once_with('/etc/puppetlabs/code/test')
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test__new', '/etc/puppetlabs/code/test__link')
        mock_rename.assert_called_once_with('/etc/puppetlabs/code/test__link', '/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test__old')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.shutil.copytree')
    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.rename')
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.listdir')
    @patch('puppet_env_manager.manager.os.path.exists')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.subprocess.Popen')
    @patch('puppet_env_manager.manager.Repo')
    def test_update_environment_dir_no_puppetfile_changes(
            self, mock_repo, mock_subprocess, mock_islink, mock_exists, mock_listdir, mock_readlink,
            mock_symlink, mock_rename, mock_rmtree, mock_copytree):
        mock_subprocess.return_value = mock_subprocess
        mock_subprocess.communicate.return_value = ('', '')
        mock_subprocess.poll.return_value = 0
        mock_repo.return_value = mock_repo
        mock_islink.return_value = False
        mock_exists.return_value = True
        mock_readlink.return_value = '/etc/puppetlabs/code/test__old'
        mock_listdir.return_value = ['one', 'two']
        self.manager.check_sync = Mock(return_value=False)
        self.manager.has_puppetfile_changed = Mock(return_value=False)
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_resource_type_cache = Mock()
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.side_effect = [
            '/etc/puppetlabs/code/test__new',
            '/etc/puppetlabs/code/test__dir',
        ]
        self.manager.new_workdir_path = '/bin/git-new-workdir'

        self.manager.update_environment('test', force=False)

        self.manager.lock_environment.assert_called_once_with('test')
        mock_repo.head.reset.assert_called_once_with(self.mock_ref.commit)
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test__new', 'test'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_copytree.assert_has_calls([
            call('/etc/puppetlabs/code/test/thirdparty/one', '/etc/puppetlabs/code/test__new/thirdparty/one', symlinks=True),
            call('/etc/puppetlabs/code/test/thirdparty/two', '/etc/puppetlabs/code/test__new/thirdparty/two', symlinks=True)
        ])
        self.assertEqual(0, self.manager.install_puppet_modules.call_count, 'install_puppet_modules should not have been called')
        self.manager.generate_resource_type_cache.assert_called_once_with('/etc/puppetlabs/code/test__new', force=False)
        mock_islink.assert_has_calls([
            call('/etc/puppetlabs/code/test'), call('/etc/puppetlabs/code/test')
        ])
        mock_rename.assert_called_once_with('/etc/puppetlabs/code/test', '/etc/puppetlabs/code/test__dir')
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test__new', '/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test__dir')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.shutil.copytree')
    @patch('puppet_env_manager.manager.shutil.rmtree')
    @patch('puppet_env_manager.manager.os.rename')
    @patch('puppet_env_manager.manager.os.symlink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.listdir')
    @patch('puppet_env_manager.manager.os.path.exists')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.subprocess.Popen')
    @patch('puppet_env_manager.manager.Repo')
    def test_update_environment_dir(
            self, mock_repo, mock_subprocess, mock_islink, mock_exists, mock_listdir, mock_readlink,
            mock_symlink, mock_rename, mock_rmtree, mock_copytree):
        mock_subprocess.return_value = mock_subprocess
        mock_subprocess.communicate.return_value = ('', '')
        mock_subprocess.poll.return_value = 0
        mock_repo.return_value = mock_repo
        mock_islink.return_value = False
        mock_exists.return_value = True
        mock_readlink.return_value = '/etc/puppetlabs/code/test__old'
        mock_listdir.return_value = ['one', 'two']
        self.manager.check_sync = Mock(return_value=False)
        self.manager.has_puppetfile_changed = Mock(return_value=True)
        self.manager.install_puppet_modules = Mock()
        self.manager.generate_resource_type_cache = Mock()
        self.manager.generate_unique_environment_path = Mock()
        self.manager.generate_unique_environment_path.side_effect = [
            '/etc/puppetlabs/code/test__new',
            '/etc/puppetlabs/code/test__dir',
        ]
        self.manager.new_workdir_path = '/bin/git-new-workdir'

        self.manager.update_environment('test', force=False)

        self.manager.lock_environment.assert_called_once_with('test')
        mock_repo.head.reset.assert_called_once_with(self.mock_ref.commit)
        mock_subprocess.assert_called_once_with([
            '/bin/sh', '/bin/git-new-workdir', '/etc/puppetlabs/code/.puppet.git',
            '/etc/puppetlabs/code/test__new', 'test'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_copytree.assert_has_calls([
            call('/etc/puppetlabs/code/test/thirdparty/one', '/etc/puppetlabs/code/test__new/thirdparty/one', symlinks=True),
            call('/etc/puppetlabs/code/test/thirdparty/two', '/etc/puppetlabs/code/test__new/thirdparty/two', symlinks=True)
        ])
        self.manager.install_puppet_modules.assert_called_once_with('/etc/puppetlabs/code/test__new')
        self.manager.generate_resource_type_cache.assert_called_once_with('/etc/puppetlabs/code/test__new', force=False)
        mock_islink.assert_has_calls([
            call('/etc/puppetlabs/code/test'), call('/etc/puppetlabs/code/test')
        ])
        mock_rename.assert_called_once_with('/etc/puppetlabs/code/test', '/etc/puppetlabs/code/test__dir')
        mock_symlink.assert_called_once_with('/etc/puppetlabs/code/test__new', '/etc/puppetlabs/code/test')
        mock_rmtree.assert_called_once_with('/etc/puppetlabs/code/test__dir')
        self.manager.unlock_environment.assert_called_once_with('test')

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.os.unlink')
    @patch('puppet_env_manager.manager.os.path.exists')
    @patch('puppet_env_manager.manager.os.path.islink')
    def test_update_environment_dir_dangling_symlink(
            self, mock_islink, mock_exists, mock_unlink):
        mock_islink.return_value = True
        mock_exists.return_value = False
        self.manager.add_environment = Mock()

        self.manager.update_environment('test', force=False)

        mock_unlink.assert_called_once_with('/etc/puppetlabs/code/test')
        self.manager.add_environment.assert_called_once_with('test', flush=True)

    @patch('puppet_env_manager.manager.LockFile')
    @patch('puppet_env_manager.manager.os.path.isdir')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.listdir')
    def test_list_stale_environment_clones(self, mock_listdir, mock_readlink, mock_islink, mock_isdir, mock_lock):
        mock_listdir.return_value = [
            '.', '..', '.puppet.git', 'production', 'production.clone',
            'test', 'test__clone', 'test__123abc', 'live_test'
        ]
        mock_islink.side_effect = [
            True, False, True, False, False
        ]
        mock_readlink.side_effect = [
            '/etc/puppetlabs/code/production.clone',
            '/etc/puppetlabs/code/test__clone',
        ]
        mock_isdir.return_value = True
        mock_lock.return_value = mock_lock
        mock_lock.is_locked.return_value = False

        stale_clones = self.manager.list_stale_environment_clones()
        self.assertListEqual(stale_clones, ['/etc/puppetlabs/code/test__123abc'])

        mock_listdir.assert_called_once_with('/etc/puppetlabs/code')
        self.assertEqual(mock_islink.call_count, 5)
        self.assertEqual(mock_isdir.call_count, 3)

    @patch('puppet_env_manager.manager.LockFile')
    @patch('puppet_env_manager.manager.os.path.isdir')
    @patch('puppet_env_manager.manager.os.path.islink')
    @patch('puppet_env_manager.manager.os.readlink')
    @patch('puppet_env_manager.manager.os.listdir')
    def test_list_stale_environment_clones_with_locked(self, mock_listdir, mock_readlink, mock_islink, mock_isdir, mock_lock):
        mock_listdir.return_value = [
            'test', 'test__clone', 'test__123abc',
        ]
        mock_islink.side_effect = [
            True, False, False
        ]
        mock_readlink.side_effect = [
            '/etc/puppetlabs/code/test__clone',
        ]
        mock_isdir.return_value = True
        mock_lock.return_value = mock_lock
        mock_lock.is_locked.return_value = True

        stale_clones = self.manager.list_stale_environment_clones()
        self.assertListEqual(stale_clones, [])

        mock_listdir.assert_called_once_with('/etc/puppetlabs/code')
        self.assertEqual(mock_islink.call_count, 3)
        self.assertEqual(mock_isdir.call_count, 2)

    # noinspection PyUnresolvedReferences
    @patch('puppet_env_manager.manager.shutil.rmtree')
    def test_cleanup_stale_environment_clones(self, mock_rmtree):
        self.manager.list_stale_environment_clones = Mock(return_value=[
            '/etc/puppetlabs/code/test__123abc', '/etc/puppetlabs/code/test__987fed'])

        self.manager.cleanup_stale_environment_clones()
        self.manager.lock_environment.assert_has_calls([call('test'), call('test')])
        mock_rmtree.assert_has_calls([
            call('/etc/puppetlabs/code/test__123abc'),
            call('/etc/puppetlabs/code/test__987fed'),
        ])
        self.manager.unlock_environment.assert_has_calls([call('test'), call('test')])


class TestEnvironmentCacheFlushing(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(environment_dir='/etc/puppetlabs/code', validate=False)
        self.manager.logger = Mock()
        self.manager.puppet_server = 'localhost'
        self.manager.puppet_cert_file = '/etc/puppetlabs/puppet/ssl/certs/localhost.pem'
        self.manager.puppet_key_file = '/etc/puppetlabs/puppet/ssl/private_keys/localhost.pem'
        self.manager.puppet_ca_file = '/etc/puppetlabs/puppet/ssl/certs/ca.pem'

    @patch('puppet_env_manager.manager.requests')
    def test_disabled_all_environments_cache_flush(self, mock_requests):
        self.manager.flush_environment_cache = False
        self.manager.flush_environment_caches()
        self.manager.logger.debug.assert_called_with("Skipping environment flush")
        self.assertEqual(0, mock_requests.delete.call_count, "requests.delete should not have been called")

    @patch('puppet_env_manager.manager.requests')
    def test_disabled_single_environment_cache_flush(self, mock_requests):
        self.manager.flush_environment_cache = False
        self.manager.flush_environment_caches(environment="test")
        self.manager.logger.debug.assert_called_with("Skipping environment flush")
        self.assertEqual(0, mock_requests.delete.call_count, "requests.delete should not have been called")

    @patch('puppet_env_manager.manager.requests')
    def test_all_environments_cache_flush(self, mock_requests):
        mock_requests.delete.return_value = Mock(status_code=204)
        self.manager.flush_environment_caches()
        mock_requests.delete.assert_called_with(
            'https://localhost:8140/puppet-admin-api/v1/environment-cache',
            params={},
            cert=(
                '/etc/puppetlabs/puppet/ssl/certs/localhost.pem',
                '/etc/puppetlabs/puppet/ssl/private_keys/localhost.pem'),
            verify='/etc/puppetlabs/puppet/ssl/certs/ca.pem',
        )

    @patch('puppet_env_manager.manager.requests')
    def test_single_environment_cache_flush(self, mock_requests):
        mock_requests.delete.return_value = Mock(status_code=204)
        self.manager.flush_environment_caches(environment='test')
        mock_requests.delete.assert_called_with(
            'https://localhost:8140/puppet-admin-api/v1/environment-cache',
            params={'environment': 'test'},
            cert=(
                '/etc/puppetlabs/puppet/ssl/certs/localhost.pem',
                '/etc/puppetlabs/puppet/ssl/private_keys/localhost.pem'),
            verify='/etc/puppetlabs/puppet/ssl/certs/ca.pem',
        )

    @patch('puppet_env_manager.manager.requests')
    def test_single_environment_cache_flush_forbidden(self, mock_requests):
        mock_requests.delete.return_value = Mock(status_code=403, text='Forbidden')
        self.manager.flush_environment_caches(environment='test')
        mock_requests.delete.assert_called_with(
            'https://localhost:8140/puppet-admin-api/v1/environment-cache',
            params={'environment': 'test'},
            cert=(
                '/etc/puppetlabs/puppet/ssl/certs/localhost.pem',
                '/etc/puppetlabs/puppet/ssl/private_keys/localhost.pem'),
            verify='/etc/puppetlabs/puppet/ssl/certs/ca.pem',
        )
        self.manager.logger.warning.assert_called_with(
            'Failed to flush environment cache with error 403: Forbidden'
        )
