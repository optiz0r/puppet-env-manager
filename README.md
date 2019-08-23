# puppet-env-manager

Tool to deploy puppet environments onto puppet masters

# Usage

For detailed usage, see:
```
puppet-env-manager --help
```

# Tests

Run tests:
```
make tests
```

# Packaging

The script ships with a Makefile that can be used to generate a native RPM
package for easy installation.

Build RPM packages:
```
make
```

On Fedora 30+, the following is also needed in `~/.rpmmacros`:
```
%__brp_mangle_shebangs_exclude ^/usr/bin/python
```

To automatically sign and publish to spacewalk, run:
```
make publish
```

# Changelog

## NEXT - 2019-08-23

* Ignore locked environments during stale cleanup
  to avoid deleting a new clone being created by
  another process running in parallel
* Handle dangling symlinks left behind by failed
  add/update by deleting and re-adding environment

## v0.4.0 - 2019-08-23

* Clone the thirdparty directory into newly created environment
  clones to speed up puppet module installation using librarian
* Add support for triggering a puppet master environment cache flush
  after modifying environment content

## v0.3.1 - 2019-08-19

* Ignore `__` paths as clones and don't try to delete them during
  cleanup. Add test for this behaviour.

## v0.3.0 - 2019-08-19

* Generate resource type cache after making code changes
* Update generated clone path names to use `__` as a separator so
  they're considered valid environment names. Required for atomic
  resource type cache generation.
* Prevent branches with `__` in the name from being treated as
  environments

## v0.2.3 - 2019-08-12

* Fixup compatibility with py2.6 for el6
  (tests won't run under py2.6)

## v0.2.2 - 2019-09-11

* Prune remote branches when fetching changes
* Fix deletion of environments for pruned remote branches
* Handle removing stale environments using relative symlinks

## v0.2.1 - 2019-08-09

* Fix installation of thirdparty modules into clone paths
* Add makefile target for tests

## v0.2.0 - 2019-08-06

* Checkout updated environment code into new directories, and manage a
  symlink pointing at the live copy of the environment. This prevents
  a partially-updated environment being served out to clients
* Lock the master repository, and environments while they're being
  modified, to prevent concurrent access issues.
* Cleanup any stale environment clone directories during update-all,
  and cleanup modes
* Don't reset clean environment which is already at the correct commit
  (unless forced, which can be used to redeploy third party modules)
* Fix typo in log message
* Add `mock` to dev requirements in `setup.py`

## v0.1.3 - 2019-07-21

* Fix reset not updating the working tree properly, and add a log entry
  if the working tree is found to be dirty after the update

## v0.1.2 - 2019-07-19

* Fix detection of git-new-workdir on machines with 4-part git versions

## v0.1.1 - 2019-07-19

* Fix mismatching config directory name between packaging and code

## v0.1 - 2019-07-19

 * First version
