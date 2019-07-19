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

## v0.1 - 2019-07-19

 * First version
