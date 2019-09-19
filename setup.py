import os
import setuptools

from distutils.core import setup
from puppet_env_manager import VERSION

setup(
    name="puppet-env-manager",
    version=VERSION,
    description="Tool to manage puppet environments using librarian-puppet",
    author="Ben Roberts",
    author_email="ben.roberts@gsacapital.com",
    url="https://github.com/optiz0r/puppet-env-manager/",
    packages=setuptools.find_packages(exclude=['tests*']),
    package_data={'demo': ['data/*']},
    scripts=[
        'bin/puppet-env-manager',
    ],
    data_files=[
        ('/etc/puppet-env-manager', []),
    ],
    install_requires=['lockfile', 'requests'],
    extra_requires={
        'dev': [
            'mock',
        ]
    }
)
