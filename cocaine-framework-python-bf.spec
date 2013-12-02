%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print (get_python_lib())")}

Name:		cocaine-framework-python
Version:	0.11.1.0
Release:	1%{?dist}
Summary:	Cocaine - Python Framework

Group:		Development/Libraries
License:	LGPLv3
URL:		http://reverbrain.com
Source0:	http://repo.reverbrain.com/sources/%{name}/%{name}-%{version}.tar.bz2
BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:	noarch

BuildRequires:	python-devel
BuildRequires:	python-setuptools

Requires:	python-msgpack
Requires:	python-tornado

%description
A simple framework to ease the developing of Cocaine apps.

%prep 
%setup -q -n %{name}-%{version}

%build


%install
rm -rf %{buildroot}

python setup.py install --root=%{buildroot}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README* LICENSE
%{python_sitelib}/*

%changelog
* Thu Jul 27 2013 Arkady L. Shane <ashejn@russianfedora.ru> - 0.10.5.5-1
- initial build
