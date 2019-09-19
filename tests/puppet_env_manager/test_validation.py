import unittest

from mock import patch

from puppet_env_manager.exceptions import InvalidConfiguration
from puppet_env_manager.manager import EnvironmentManager


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(
            git_url='https://example.com/puppet.git',
            upstream_remote='origin',
            environment_dir='/etc/puppetlabs/code',
            validate=False
        )

    def test_validate_git_url(self):
        """ Verifies blacklisted environment names are correctly detected
        """
        self.manager.git_url = None
        with self.assertRaises(InvalidConfiguration) as cm:
            self.manager.validate_settings()

        self.assertEqual(cm.exception.args[0], 'Git URL must be specified')

    def test_validate_upstream_repo(self):
        self.manager.upstream_remote = None
        with self.assertRaises(InvalidConfiguration) as cm:
            self.manager.validate_settings()

        self.assertEqual(cm.exception.args[0], 'Upstream remote name must be specified')

    @patch('puppet_env_manager.manager.os.path.exists', return_value=True)
    def test_validate_environment_dir_exists(self, mock_exists):
        self.manager.validate_settings()
        mock_exists.assert_any_call('/etc/puppetlabs/code')

    @patch('puppet_env_manager.manager.os.path.exists', return_value=False)
    def test_validate_environment_dir_doesnt_exist(self, mock_exists):
        with self.assertRaises(InvalidConfiguration) as cm:
            self.manager.validate_settings()

        mock_exists.assert_any_call('/etc/puppetlabs/code')
        self.assertEqual(cm.exception.args[0], 'Environment directory /etc/puppetlabs/code not found or not readable')


    # TODO: missing tests
    # new-workdir found
    # new-workdir not found
    # librarian-puppet path absolute path returned
    # librarian-puppet path relative found
    # librarian-puppet path relative not found