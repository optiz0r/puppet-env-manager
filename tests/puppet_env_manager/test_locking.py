import unittest

from mock import call, patch

from puppet_env_manager.manager import EnvironmentManager


class TestLocks(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(
            git_url='https://example.com/puppet.git',
            upstream_remote='origin',
            environment_dir='/etc/puppetlabs/code',
            validate=False
        )

    @patch('puppet_env_manager.manager.LockFile')
    def test_lock(self, mock_lock):
        mock_lock.return_value = mock_lock
        self.manager.lock_environment('production')

        mock_lock.assert_called_with('/etc/puppetlabs/code/production')
        mock_lock.acquire.assert_called_once_with()
        self.assertIn('/etc/puppetlabs/code/production', self.manager._locks)

    @patch('puppet_env_manager.manager.LockFile')
    def test_unlock_locked_environment(self, mock_lock):
        self.manager._locks = {
            '/etc/puppetlabs/code/production': mock_lock,
        }

        self.manager.unlock_environment('production')

        mock_lock.release.assert_called_once()
        self.assertEqual(self.manager._locks, {})

    def test_unlock_unlocked_environment(self):
        locks = {
            '/etc/puppetlabs/code/production': None,
        }
        self.manager._locks = locks.copy()

        self.manager.unlock_environment('qa')

        self.assertDictEqual(locks, self.manager._locks)
