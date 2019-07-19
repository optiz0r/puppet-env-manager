import unittest

from puppet_env_manager.manager import EnvironmentManager


class TestUtils(unittest.TestCase):
    def setUp(self):
        self.manager = EnvironmentManager(validate=False)

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
