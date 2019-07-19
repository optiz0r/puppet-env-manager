import unittest

from puppet_env_manager.manager import EnvironmentManager


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(validate=False)

    def test_validate_environment_name(self):
        """ Verifies blacklisted environment names are correctly detected
        """
        good_names = ['production', 'develop', 'feature_branch', 'feature_branch123']
        bad_names = ['live_foo']

        for name in good_names:
            self.assertTrue(self.manager.validate_environment_name(name))

        for name in bad_names:
            self.assertFalse(self.manager.validate_environment_name(name))
