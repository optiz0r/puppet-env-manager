# puppet-env-manager

Tool to deploy puppet environments onto puppet masters

# Usage

For detailed usage, see:
```
puppet-env-manager --help
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

# Changelog

## NEXT - TBC

* Fix installation of thirdparty modules into clone paths

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
