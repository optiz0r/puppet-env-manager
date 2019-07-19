import os

from distutils.core import setup
from puppet_env_manager import VERSION

setup(
    name="puppet-env-manager",
    version=VERSION,
    description="Tool to manage puppet environments using librarian-puppet",
    author="Ben Roberts",
    author_email="ben.roberts@gsacapital.com",
    url="https://github.com/optiz0r/puppet-env-manager/",
    package_dir={'': 'src/lib'},
    packages=['puppet_env_manager'],
    package_data={'demo': ['data/*']},
    scripts=[
        'src/bin/puppet-env-manager',
    ],
    data_files=[
        ('/etc/puppet-env-manager', []),
    ]
)
