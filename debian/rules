#!/usr/bin/make -f

DEB_PYTHON_SYSTEM=pycentral

include /usr/share/cdbs/1/rules/debhelper.mk
include /usr/share/cdbs/1/class/python-distutils.mk

package=cocaine-framework-python

install/cocaine-framework-python::
	for pv in $(shell pyversions -vr debian/control); do \
	cp cocaine/__init__.py debian/$(package)/usr/lib/python$$pv/*-packages/cocaine/; \
	done
