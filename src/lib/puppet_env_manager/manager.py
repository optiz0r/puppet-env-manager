import logging
import os
import random
import re
import shutil
import string
import subprocess

from distutils.spawn import find_executable
from git import Repo
from git.cmd import Git
# noinspection PyProtectedMember
from lockfile import LockFile

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

        self._locks = {}

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
        self.lock_path(self.master_repo_path)

        self.logger.debug(self._noop("Fetching changes from {0}".format(self.upstream_remote)))
        if not self.noop:
            remote = self.master_repo.remote(self.upstream_remote)
            fetch_info = remote.fetch()
            for fetch in fetch_info:
                self.logger.debug("Updated {0} to {1}".format(fetch.ref, fetch.commit))

        self.unlock_path(self.master_repo_path)

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

    def lock_path(self, path):
        """ Obtains a lock on the given path

        Paths are locked by creating an `.lock` file next to the environment directory.
        Files are created in exclusive mode to guarantee atomicity using the filesystem as the arbiter.
        If an environment is already locked, blocks waiting for the environment to become free.

        Obtained locks are stored in the manager so they can be cleaned up on exit.

        In noop mode, locking operations are faked and assumed to have always succeeded.

        :param path: str Path to be locked
        """
        self.logger.debug("Acquiring lock for {0}".format(path))
        if not self.noop:
            lock = LockFile(path)
            lock.acquire()
            self._locks[path] = lock

        self.logger.debug("Lock acquired for {0}".format(path))

    def unlock_path(self, path):
        """ Releases a lock held on the given path

        :param path: str Path to locked file
        """
        if path not in self._locks:
            return

        if not self.noop:
            lock = self._locks.pop(path)
            lock.release()

        self.logger.debug("Released lock for {0}".format(path))

    def unlock_all_paths(self):
        """ Releases all locks held by this process

        To be called during abnormal process exit to try and avoid leaving stale locks around
        """
        for path in self._locks:
            if not self.noop:
                self._locks[path].release()

        self._locks = {}

        self.logger.debug("All locks released")

    def lock_environment(self, environment):
        """ Obtains a lock on the given environment name

        Environments are locked by creating an `.lock` file next to the environment directory.
        Files are created in exclusive mode to guarantee atomicity using the filesystem as the arbiter.
        If an environment is already locked, blocks waiting for the environment to become free.

        Obtained locks are stored in the manager so they can be cleaned up on exit.

        In noop mode, locking operations are faked and assumed to have always succeeded.

        :param environment: str Environment name
        """
        repo_path = self.environment_repo_path(environment)
        self.lock_path(repo_path)

    def unlock_environment(self, environment):
        """ Releases a lock held on the given environment name

        :param environment: str Environment name
        """
        repo_path = self.environment_repo_path(environment)
        self.unlock_path(repo_path)

    def unlock_all_environments(self):
        """ Releases all locks held by this process

        To be called during abnormal process exit to try and avoid leaving stale locks around
        """
        self.unlock_all_paths()

    def environment_repo(self, environment):
        """ Returns the git Repo object for an environment repository

        :param environment: str Environment name
        :return: git.Repo
        """
        path = self.environment_repo_path(environment)
        if not path:
            return None

        return Repo(path)

    def environment_repo_path(self, environment):
        """ Returns the path to the git working tree for an environment

        :param environment: str Environment name
        :return: str path
        """
        if not self.validate_environment_name(environment):
            self.logger.error("Cannot get repository for {0} with invalid name".format(environment))
            return None

        return os.path.join(self.environment_dir, environment)
    
    def generate_unique_environment_path(self, environment):
        """ Returns a unique path for an environment working copy to be located at
        
        This function will generate the path to use for a new directory under the environment dir
        based on the given environment name, but with a unique suffix. This will be the target for an
        environment symlink which can be updated atomically.
        
        :param environment: str Environment name
        :return: str path
        """
        
        while True:
            tmp = ''.join(random.choice(string.hexdigits) for _ in range(6))
            path = os.path.join(self.environment_dir, "{0}.{1}".format(environment, tmp))

            if not os.path.exists(path):
                return path

    def upstream_ref(self, environment):
        """ Returns the upstream ref for the given environment from the master repo

        :param environment: str Environment name
        :return: git.Ref
        """
        # noinspection PyUnresolvedReferences
        upstream_ref = self.master_repo.refs["{0}/{1}".format(self.upstream_remote, environment)]
        return upstream_ref

    @staticmethod
    def check_sync(repo, upstream_ref):
        """ Checks if the HEAD of the given repo is in sync

        Returns True if the repo is in sync with upstream, False otherwise

        :param repo: git.Repo Repository to check
        :param upstream_ref: git.Ref Reference the upstream repository is at to compare with
        :return: bool
        """
        in_sync = (upstream_ref.commit == repo.head.commit) and not repo.is_dirty()
        return in_sync

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

        self.lock_environment(environment)

        self.logger.info(self._noop("Adding environment {0}".format(environment)))

        environment_path = os.path.join(self.environment_dir, environment)
        clone_path = self.generate_unique_environment_path(environment)

        cmd = ['/bin/sh', self.new_workdir_path, self.master_repo_path, clone_path, environment]
        self.logger.debug(self._noop("Running command: {0}".format(" ".join(cmd))))
        if not self.noop:
            try:
                output = subprocess.check_output(cmd)
                self.logger.debug(output)

                os.symlink(clone_path, environment_path)
                self.logger.debug("Linked {0} to {1}".format(environment_path, clone_path))
            except subprocess.CalledProcessError as e:
                self.logger.error("Failed to add environment {0}, exited {1}: {2}".format(
                    environment, e.returncode, e.output))

                self.unlock_environment(environment)

                return

        self.install_puppet_modules(environment)

        self.unlock_environment(environment)

    def update_environment(self, environment, force=False):
        """ Updates an existing environment in the environment directory by name

        :param environment: Environment name
        :param force: Force reset of environment even if it already appears to be up to date
        :return:
        """
        repo_path = self.environment_repo_path(environment)
        if not repo_path:
            return

        self.lock_environment(environment)

        repo = Repo(repo_path)

        upstream_ref = self.upstream_ref(environment)
        if self.check_sync(repo, upstream_ref):
            self.logger.info("{0} already up to date at {1}".format(environment, upstream_ref.commit.hexsha))
            if not force:
                self.unlock_environment(environment)
                return

        self.logger.info(self._noop("Resetting {0} to {1} ({2})".format(
            environment, upstream_ref.commit.hexsha, upstream_ref.name)))

        if not self.noop:
            repo.head.reset(upstream_ref.commit)

        # Clone the environment first, so we can do the update atomically
        clone_path = self.generate_unique_environment_path(environment)

        cmd = ['/bin/sh', self.new_workdir_path, self.master_repo_path, clone_path, environment]
        self.logger.debug(self._noop("Running command: {0}".format(" ".join(cmd))))
        if not self.noop:
            try:
                output = subprocess.check_output(cmd)
                self.logger.debug(output)
            except subprocess.CalledProcessError as e:
                self.logger.error("Failed to add environment {0}, exited {1}: {2}".format(
                    environment, e.returncode, e.output))

        self.install_puppet_modules(environment)

        if os.path.islink(repo_path):
            old_clone = os.readlink(repo_path)
            temp_link = self.generate_unique_environment_path(environment)

            if not self.noop:
                os.symlink(clone_path, temp_link)
                self.logger.debug("Creating temporary symlink to {0} at {1}".format(environment, temp_link))

                os.rename(temp_link, repo_path)
                self.logger.debug("Atomically replacing symlink to {0}".format(environment))

                shutil.rmtree(old_clone)
                self.logger.debug("Removed old copy of {0} from {1}".format(environment, old_clone))

            self.logger.debug(self._noop("Updated {0} symlink to {1}".format(environment, clone_path)))

        else:
            self.logger.warning("{0} is not currently a symlink, update is happening non-atomically".format(
                environment))

            temp_path = self.generate_unique_environment_path(environment)

            if not self.noop:
                # To minimise window where environment is not available, move it out of the way and symlink the
                # new clone back into place. Deleting the entire directory tree for the old clone will take
                # significantly longer to do.
                os.rename(repo_path, temp_path)
                self.logger.debug("Moved {0} to temporary path {1}".format(environment, temp_path))

                os.symlink(clone_path, repo_path)
                self.logger.debug("Created symlink for {0} to {1}".format(environment, clone_path))

                shutil.rmtree(temp_path)
                self.logger.debug("Removed old copy of {0} from {1}".format(environment, temp_path))

            self.logger.debug("Replaced {0} directory with symlink to {1}".format(environment, clone_path))

        self.unlock_environment(environment)

    def remove_environment(self, environment):
        """ Deletes an existing environment from the environment directory by name

        :param environment: Environment name
        :return:
        """
        repo_path = self.environment_repo_path(environment)
        if not repo_path:
            self.logger.warning("Not removing environment {0} with invalid name".format(environment))
            return

        self.logger.info(self._noop("Deleting environment {0}".format(environment)))
        if os.path.islink(repo_path):
            # Find what the link points at
            target_path = os.readlink(repo_path)

            self.logger.debug(self._noop("Removing symlink {0} and target {1}".format(repo_path, target_path)))

            if not self.noop:
                os.unlink(repo_path)
                shutil.rmtree(target_path)
        else:
            if not self.noop:
                shutil.rmtree(repo_path)

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

    def list_stale_environment_clones(self):
        """ Lists environment clones left behind on disk and no longer used

        Stale clones could be left behind because of an error during a previous run.

        An environment is defined as stale if it fits the name of a managed environment
        with a suffix, and is not pointed at by any symlinks

        :return: list(str)
        """
        links = {}
        candidates = []
        stale_clones = []

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

            path = os.path.join(self.environment_dir, item)
            if os.path.islink(path):
                links[os.readlink(path)] = path
            elif os.path.isdir(path):
                candidates.append(path)

        # Look for candidate environments which aren't the target of any symlinks
        for candidate in candidates:
            if candidate not in links:
                self.logger.debug("Stale environment detected: {0}".format(candidate))
                stale_clones.append(candidate)

        return stale_clones

    def cleanup_stale_environment_clones(self):
        """ Removes stale environment clones found by list_stale_environment_clones
        """
        stale_clones = self.list_stale_environment_clones()
        for clone_path in stale_clones:
            # Determine the environment this clone is for
            environment = re.sub(r'^(?:.*/)?([^./]+)\.[^.]+$', r'\1', clone_path)

            self.lock_environment(environment)

            self.logger.info(self._noop("Removing stale environment clone {0}".format(clone_path)))
            if not self.noop:
                shutil.rmtree(clone_path)

            self.unlock_environment(environment)

    @staticmethod
    def find_executable(name):
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

            # Ignore anything with dots (lock files, temporary clones)
            if '.' in item:
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

    def update_single_environment(self, environment, force=False):
        """ Updates a single environment by name

        :param environment: Environment name
        :param force: Force reset of environment even if it already appears to be up to date
        :return:
        """
        self.check_master_repo()
        self.fetch_changes()
        if environment not in self.list_installed_environments():
            self.add_environment(environment)
        else:
            self.update_environment(environment, force=force)

    def update_all_environments(self, force=False):
        """ Updates all environments to latest content, and removes obsolete environments

        :param force: Force reset of environment even if it already appears to be up to date
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
            self.update_environment(environment, force=force)

        self.cleanup_environments(removed)

    def cleanup_environments(self, removed=None):
        """ Removes environments from local disk

        - If `removed` is an iterable, those environments will be removed from local disk.
        - If `removed` is not provided, the set of environments to be removed is calculated by comparing local
          and upstream environments

        Also removes any stale environment clones (which might have been left behind due to an error during deploy)

        :param removed: list of environments to be removed, optional
        :return:
        """
        if removed is None:
            removed = self.list_obsolete_environments()

        for environment in removed:
            self.remove_environment(environment)

        self.cleanup_stale_environment_clones()
