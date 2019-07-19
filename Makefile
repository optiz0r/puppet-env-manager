PROJECT := puppet-env-manager

# Package metadata
ITERATION  := 1

OS := $(shell facter -p operatingsystem)

ifeq ($(OS),Fedora)
	DIST  := .fc$(shell facter -p os.release.major)
	PYTHON_PREFIX := python2
	PYTHON3_PREFIX := python3
else ifeq ($(OS),CentOS)
	DIST := .el$(shell facter -p os.release.major)
	PYTHON_PREFIX := python
	PYTHON3_PREFIX := python36
else ifeq ($(OS),RedHat)
	DIST := .el$(shell facter -p os.release.major)
	PYTHON_PREFIX := python
else
	DIST :=
	PYTHON_PREFIX := python
endif

RELEASE := $(ITERATION)$(DIST)

# Build targets
default: rpm

rpm:
		@echo "# Packaging for python"
		env PYTHONPATH=./src/lib python ./setup.py bdist_rpm --release ${RELEASE} --python python

rpm-python3:
		@echo "# Packaging for python3"
		env PYTHONPATH=./src/lib python3 ./setup.py bdist_rpm --release ${RELEASE} --python python3

clean:
		rm -rf src/lib/$(PROJECT).egg-info/

clobber: clean
		rm -f *.rpm

# vim: set ts=4 shiftwidth=4 noexpandtab:
