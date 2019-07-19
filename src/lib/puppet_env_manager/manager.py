import logging
import os
import re
import shutil
import subprocess

from distutils.spawn import find_executable
from git import Repo
from git.cmd import Git

from .config import EnvironmentManagerConfig
from .exceptions import MasterRepositoryMissing, InvalidConfiguration

__ALL__ = ('EnvironmentManager',)


class EnvironmentManager(object):
    ENVIRONMENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')

    def __init__(
            self,
            git_url=EnvironmentManagerConfig.GIT_URL,
            environment_dir=EnvironmentManagerConfig.ENVIRONMENT_DIR,
            master_repo_name=EnvironmentManagerConfig.MASTER_REPO_NAME,
            blacklist=EnvironmentManagerConfig.ENVIRONMENT_NAME_BLACKLIST,
            upstream_remote=EnvironmentManagerConfig.UPSTREAM_REMOTE,
            librarian_puppet_path=EnvironmentManagerConfig.LIBRARIAN_PUPPET_PATH,
            noop=False,
            validate=True):

        self.logger = logging.getLogger(__name__)

        self.git_url = git_url
        self.environment_dir = environment_dir
        self.master_repo_name = master_repo_name
        self.upstream_remote = upstream_remote
        self.noop = noop

        self.blacklist = blacklist
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if not isinstance(self.blacklist, re._pattern_type):
            self.blacklist = re.compile(self.blacklist)

        self.master_repo_path = os.path.join(self.environment_dir, self.master_repo_name)
        self._master_repo = None

        self.librarian_puppet_path = self.find_executable(librarian_puppet_path)
        self.new_workdir_path = self.find_workdir()

        if validate:
            # Allow disabling validation to aid in testing
            self.validate_settings()

    # Helper methods

    def validate_settings(self):
        """ Basic error checking on the initialisation parameters

        :raises InvalidConfiguration
        """
        if not self.git_url:
            raise InvalidConfiguration('Git URL must be specified')

        if not os.path.exists(self.environment_dir):
            raise InvalidConfiguration('Environment directory {0} not found or not readable'.format(
                self.environment_dir))

        if not self.upstream_remote:
            raise InvalidConfiguration('Upstream remote name must be specified')

        if self.new_workdir_path is None:
            raise InvalidConfiguration('git-new-workdir script not found or not readable')

        if not os.path.exists(self.librarian_puppet_path):
            raise InvalidConfiguration('Librarian-puppet {0} not found or not readable'.format(
                self.librarian_puppet_path))

    @property
    def master_repo(self):
        if not self._master_repo:
            self._master_repo = self._get_or_create_master_repo()
        return self._master_repo

    def _get_or_create_master_repo(self):
        """ Returns a GitPython repo object for the master repository, and creates it on disk if missing

        :return: Repo|None
        """
        if os.path.exists(self.master_repo_path):
            master_repo = Repo(self.master_repo_path)
        else:
            self.logger.info("Creating master repository {0}".format(self.master_repo_path))

            if self.noop:
                self.logger.error("Master repository does not exist, further operations cannot be simulated properly")
                return None

            master_repo = Repo.init(self.master_repo_path, bare=False)
            master_repo.create_remote(self.upstream_remote, self.git_url)

        return master_repo

    def check_master_repo(self):
        """ Verifies the master repository is available

        :raise MasterRepositoryMissing if the master repository does not exist and running in noop mode
            so cannot be created
        :return:
        """
        if self.master_repo is None:
            raise MasterRepositoryMissing("Master Repository does not exist")

    def fetch_changes(self):
        """ Fetches the latest git changes into the master directory

        :return:
        """
        self.logger.debug(self._noop("Fetching changes from {0}".format(self.upstream_remote)))
        if not self.noop:
            remote = self.master_repo.remote(self.upstream_remote)
            fetch_info = remote.fetch()
            for fetch in fetch_info:
                self.logger.debug("Updated {0} to {1}".format(fetch.ref, fetch.commit))

    def validate_environment_name(self, environment):
        """ Returns true if the given environment name is valid for use with puppet

        :param environment: Environment name
        :return:
        """
        if not self.ENVIRONMENT_NAME_PATTERN.match(environment):
            return False

        if self.blacklist.match(environment):
            return False

        return True

    def environment_repo(self, environment):
        """ Returns the git Repo object for an environment repository

        :param environment: str Environment name
        :return: git.Repo
        """
        if not self.validate_environment_name(environment):
            self.logger.error("Cannot get repository for {0} with invalid name".format(environment))
            return None

        repo = Repo(os.path.join(self.environment_dir, environment))
        return repo

    def install_puppet_modules(self, environment):
        """ Installs all puppet modules using librarian-puppet

        :param environment: Environment name
        :return:
        """
        self.logger.info(self._noop("Installing puppet modules for environment {0}".format(environment)))

        environment_path = os.path.join(self.environment_dir, environment)

        cmd = [self.librarian_puppet_path, 'install']
        self.logger.debug(self._noop("Running command: {0}".format(" ".join(cmd))))
        if not self.noop:
            try:
                output = subprocess.check_output(cmd, cwd=environment_path)
                self.logger.debug(output)
            except subprocess.CalledProcessError as e:
                self.logger.error("Failed to install puppet modules into environment {0}, exited {1}: {2}".format(
                    environment, e.returncode, e.output))

                return

    def add_environment(self, environment):
        """ Checks out a new environment into the environment directory by name

        :param environment: Environment name
        :return:
        """
        # Safety first
        if not self.validate_environment_name(environment):
            self.logger.warning("Not adding environment {0} with invalid name".format(environment))
            return

        self.logger.info(self._noop("Adding environment {0}".format(environment)))

        environment_path = os.path.join(self.environment_dir, environment)

        cmd = ['/bin/sh', self.new_workdir_path, self.master_repo_path, environment_path, environment]
        self.logger.debug(self._noop("Running command: {0}".format(" ".join(cmd))))
        if not self.noop:
            try:
                output = subprocess.check_output(cmd)
                self.logger.debug(output)
            except subprocess.CalledProcessError as e:
                self.logger.error("Failed to add environment {0}, exited {1}: {2}".format(
                    environment, e.returncode, e.output))

                return

        self.install_puppet_modules(environment)

    def update_environment(self, environment):
        """ Updates an existing environment in the environment directory by name

        :param environment: Environment name
        :return:
        """
        repo = self.environment_repo(environment)
        if not repo:
            return

        upstream_ref = self.master_repo.refs["{0}/{1}".format(self.upstream_remote, environment)]
        self.logger.info(self._noop("Resetting {0} to {1} ({2}".format(
            environment, upstream_ref.commit.hexsha, upstream_ref.name)))
        if not self.noop:
            repo.head.reset(upstream_ref)

        self.install_puppet_modules(environment)

    def remove_environment(self, environment):
        """ Deletes an existing environment from the environment directory by name

        :param environment: Environment name
        :return:
        """
        # Safety first
        if not self.validate_environment_name(environment):
            self.logger.warning("Not removing environment {0} with invalid name".format(environment))
            return

        self.logger.info(self._noop("Deleting environment {0}".format(environment)))
        if not self.noop:
            shutil.rmtree(os.path.join(self.environment_dir, environment))

    @staticmethod
    def added_environments(installed_set, available_set):
        """ Returns the set of environments present upstream but missing from local disk

        :param available_set: set of environment names that exist upstream
        :param installed_set: set of environment names that exist on disk
        :return: set of environment names
        """
        added = list(available_set - installed_set)
        return added

    @staticmethod
    def existing_environments(installed_set, available_set):
        """ Returns the set of environments present both upstream and on disk

        :param available_set: set of environment names that exist upstream
        :param installed_set: set of environment names that exist on disk
        :return: set of environment names
        """
        existing = list(available_set.intersection(installed_set))
        return existing

    @staticmethod
    def removed_environments(installed_set, available_set):
        """ Returns the set of environments present on local disk but missing upstream

        :param available_set: set of environment names that exist upstream
        :param installed_set: set of environment names that exist on disk
        :return: set of environment names
        """
        removed = list(installed_set - available_set)
        return removed

    def calculate_environment_changes(self, installed_set, available_set):
        """ Given two lists of installed and available environments, generates the subset of new, common and removed

        :param available_set: set of environment names that exist upstream
        :param installed_set: set of environment names that exist on disk
        :return (added, existing, removed) lists of environments
        """
        return (self.added_environments(installed_set, available_set),
                self.existing_environments(installed_set, available_set),
                self.removed_environments(installed_set, available_set))

    def find_executable(self, name):
        """ Resolves the given name into a full executable by looking in PATH

        :param name: filename or path to the executable
        :return: str Full path to the executable, or original name if qualified or cannot be found
        """
        if name.startswith('/'):
            return name

        found = find_executable(name)
        if found:
            return found

        return name

    def find_workdir(self):
        """ Check known directories for the location of the git-new-workdir script

        :return: str path to git-new-workdir, or None if not found
        """
        version_info = Git().version_info
        version_string = ".".join([str(i) for i in version_info])

        known_paths = [
            '/usr/share/doc/git/contrib/workdir/git-new-workdir',
            '/usr/share/doc/git-{0}/contrib/workdir/git-new-workdir'.format(version_string),
        ]

        for path in known_paths:
            if os.path.exists(path):
                self.logger.debug("Located git-new-workdir at {0}".format(path))
                return path

        return None

    def _noop(self, message):
        if self.noop:
            return message + " (noop)"
        else:
            return message

    # Public methods

    def initialise(self):
        """ Initialises a new puppet environment directory

        - Clones the git repository into the master directory
        - Creates the initial environment working copies for each git branch with a valid environment name
        """
        self.check_master_repo()
        self.fetch_changes()
        self.update_all_environments()

    def list_available_environments(self):
        """ Returns a list of the environments which exist as git branches in the master directory

        :return:
        """
        environments = []
        refs = self.master_repo.remote(self.upstream_remote).refs
        for ref in refs:
            if self.validate_environment_name(ref.remote_head):
                environments.append(ref.remote_head)

        return environments

    def list_installed_environments(self):
        """ Lists all environments which have been deployed into the environment directory

        :return: list
        """
        environments = []

        items = os.listdir(self.environment_dir)
        for item in items:
            # Ignore hidden files
            if item.startswith('.'):
                continue

            # Explicitly ignore the master repo name
            if item == self.master_repo_name:
                continue

            # Ignore anything matching the blacklist pattern
            if self.blacklist.match(item):
                self.logger.debug("Ignoring blacklisted environment {0}".format(item))
                continue

            environments.append(item)

        return environments

    def list_missing_environments(self):
        """ Lists which environments exist upstream but have not been installed locally

        :return: list
        """
        self.check_master_repo()
        self.fetch_changes()
        added = self.added_environments(
            installed_set=set(self.list_installed_environments()),
            available_set=set(self.list_available_environments()))
        return added

    def list_obsolete_environments(self):
        """ Lists which environments exist locally but no longer exist upstream

        :return: list
        """
        self.check_master_repo()
        self.fetch_changes()
        removed = self.removed_environments(
            installed_set=set(self.list_installed_environments()),
            available_set=set(self.list_available_environments()))
        return removed

    def revision(self, environment):
        """ Returns the revision of the given environment as it exists on disk in the environment directory

        :param environment: Environment name
        :return:
        """
        repo = self.environment_repo(environment)
        if not repo:
            return None

        return repo.head.commit

    def update_single_environment(self, environment):
        """ Updates a single environment by name

        :param environment: Environment name
        :return:
        """
        self.check_master_repo()
        self.fetch_changes()
        if environment not in self.list_installed_environments():
            self.add_environment(environment)
        else:
            self.update_environment(environment)

    def update_all_environments(self):
        """ Updates all environments to latest content, and removes obsolete environments

        :return:
        """
        self.check_master_repo()
        self.fetch_changes()

        added, existing, removed = self.calculate_environment_changes(
            available_set=set(self.list_available_environments()),
            installed_set=set(self.list_installed_environments()))

        for environment in added:
            self.add_environment(environment)

        for environment in existing:
            self.update_environment(environment)

        self.cleanup_environments(removed)

    def cleanup_environments(self, removed=None):
        """ Removes environments from local disk

        - If `removed` is an iterable, those environments will be removed from local disk.
        - If `removed` is not provided, the set of environments to be removed is calculated by comparing local
          and upstream environments

        :param removed: list of environments to be removed, optional
        :return:
        """
        if removed is None:
            removed = self.list_obsolete_environments()

        for environment in removed:
            self.remove_environment(environment)

