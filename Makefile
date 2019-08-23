PROJECT := puppet-env-manager

# Package metadata
ITERATION  := 1

OS := $(shell facter -p operatingsystem 2>/dev/null)
VERSION := $(shell ./setup.py --version 2>/dev/null)
REPO := example

ifeq ($(OS),Fedora)
	DIST  := .fc$(shell facter -p os.release.major 2>/dev/null)
	CHANNEL := ${REPO}-fedora$(shell facter -p os.release.major 2>/dev/null)-x86_64
	PYTHON_PREFIX := python2
	PYTHON3_PREFIX := python3
else ifeq ($(OS),CentOS)
	DIST := .el$(shell facter -p os.release.major 2>/dev/null)
	CHANNEL := ${REPO}-centos$(shell facter -p os.release.major 2>/dev/null)-x86_64
	PYTHON_PREFIX := python
	PYTHON3_PREFIX := python36
else ifeq ($(OS),RedHat)
	DIST := .el$(shell facter -p os.release.major 2>/dev/null)
	CHANNEL := ${REPO}-rhel$(shell facter -p os.release.major 2>/dev/null)-x86_64
	PYTHON_PREFIX := python
else
	DIST :=
	CHANNEL :=
	PYTHON_PREFIX := python
endif

RELEASE := $(ITERATION)$(DIST)

RPM := dist/${PROJECT}-${VERSION}-${RELEASE}.noarch.rpm

# Build targets
default: rpm

${RPM}:
	@echo "# Packaging for python"
	python ./setup.py bdist_rpm --release ${RELEASE} --python python

rpm: ${RPM}

rpm-python3:
	@echo "# Packaging for python3"
	python3 ./setup.py bdist_rpm --release ${RELEASE} --python python3

clean:
	rm -rf $(PROJECT).egg-info/

clobber: clean
	rm -f *.rpm

# Release targets

${RPM}.signed: ${RPM}
	rpm --resign ${RPM}
	touch ${RPM}.signed

sign: ${RPM}
	rpm --resign ${RPM}
	touch ${RPM}.signed

publish: ${RPM}.signed
	rhnpush -c ${CHANNEL} ${RPM}

# Test targets

test:
	python -m unittest discover

# vim: set ts=4 shiftwidth=4 noexpandtab:
