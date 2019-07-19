class EnvironmentManagerException(Exception):
    pass


class MasterRepositoryMissing(EnvironmentManagerException):
    pass


class InvalidConfiguration(EnvironmentManagerException):
    pass
