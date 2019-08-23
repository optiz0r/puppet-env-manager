import unittest

from puppet_env_manager.manager import EnvironmentManager


class TestNames(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(validate=False)

    def test_validate_environment_name(self):
        """ Verifies blacklisted environment names are correctly detected
        """
        good_names = ['production', 'develop', 'feature_branch', 'feature_branch123']
        bad_names = ['live_foo', 'production__clone']

        for name in good_names:
            self.assertTrue(self.manager.validate_environment_name(name))

        for name in bad_names:
            self.assertFalse(self.manager.validate_environment_name(name))

    def test_identify_environment_name_from_path(self):
        """ Verifies the environment name is correctly extracted from a path string
        """

        mappings = [
            ('/etc/puppetlabs/code/production', 'production'),
            ('/etc/puppetlabs/code/production__clone', 'production__clone'),
            ('/etc/puppetlabs/code/production__clone/', 'production__clone'),
        ]

        for mapping in mappings:
            self.assertEqual(self.manager.identify_environment_name_from_path(mapping[0]), mapping[1])

    def test_identify_environment_name_from_clone_name(self):
        """ Verifies the environment name is correctly extracted from a clone name
        """

        mappings = [
            ('test__abc', 'test'),
            ('test', 'test'),
            ('test__abc__def', 'test'),
        ]

        for mapping in mappings:
            self.assertEqual(mapping[1], self.manager.identify_environment_name_from_clone_name(mapping[0]))