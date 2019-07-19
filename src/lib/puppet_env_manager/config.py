import logging
import os
import yaml


__ALL__ = ('EnvironmentManagerConfig',)


class BaseConfig(object):
    """ Base configuration handler deals with configuration file loading, and merging

    Should be subclassed to provide the defined settings
    """

    def __init__(self, path):
        self.logger = logging.getLogger(__name__)
        self.path = path
        self.config = {}

    def load(self):
        """ Load settings from config file

        :return:
        """
        if not os.path.exists(self.path):
            self.logger.debug("Could not load config file, {0} does not exist or is not readable".format(self.path))
            return

        with open(self.path, 'rb') as f:
            loaded_config = yaml.safe_load(f)

            if type(loaded_config) is not dict:
                self.logger.warning(
                    'Configuration file must be a dictionary, not {0}; ignored'.format(type(loaded_config)))
                return

            for key in loaded_config:
                if key not in self.config:
                    self.logger.warning('Invalid key in configuration file, {0}; ignored'.format(key))
                    continue

                self.config[key] = loaded_config[key]

    def merge(self, **kwargs):
        """ Merge non-null keyword arguments into the config

        :param kwargs:
        :return:
        """
        for key in kwargs:
            if key not in self.config:
                self.logger.warning('Invalid key in merge, {0}; ignored'.format(key))
                continue

            if kwargs[key] is not None:
                self.config[key] = kwargs[key]

    def get_config(self):
        """ Return a copy of the config

        :return: dict
        """
        return self.config.copy()

    def as_yaml(self):
        """ Returns a copy of the config as a yaml document

        :return: str
        """
        return yaml.dump(self.config, default_flow_style=False, explicit_start=True)


class EnvironmentManagerConfig(BaseConfig):

    DEFAULT_PATH = '/etc/puppet-environment-manager/config.yaml'

    GIT_URL = None
    ENVIRONMENT_DIR = '/data/puppet/environments'
    MASTER_REPO_NAME = '.puppet.git'
    ENVIRONMENT_NAME_BLACKLIST = r'^live_.*$'
    UPSTREAM_REMOTE = 'origin'
    LIBRARIAN_PUPPET_PATH = '/opt/puppetlabs/puppet/bin/librarian-puppet'

    def __init__(self, path=DEFAULT_PATH):
        super(EnvironmentManagerConfig, self).__init__(path=path)
        self.config = {
            'git_url': self.GIT_URL,
            'environment_dir': self.ENVIRONMENT_DIR,
            'master_repo_name': self.MASTER_REPO_NAME,
            'blacklist': self.ENVIRONMENT_NAME_BLACKLIST,
            'upstream_remote': self.UPSTREAM_REMOTE,
            'librarian_puppet_path': self.LIBRARIAN_PUPPET_PATH,
        }
