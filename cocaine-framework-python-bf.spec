%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print (get_python_lib())")}

Name:		cocaine-framework-python
Version:	0.10.6.6
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


%package -n cocaine-tools
Summary:	Cocaine - Toolset
Group:		Development/Libraries
Requires:	cocaine-framework-python = %{version}-%{release}
Requires:	python-opster >= 4.0


%description -n cocaine-tools
Various tools to query and manipulate running Cocaine instances.


%package -n cocaine-tornado-proxy
Summary:	Cocaine - HTTP proxy
Group:		Development/Libraries
Requires:	cocaine-framework-python = %{version}-%{release}


%description -n cocaine-tornado-proxy
HTPP entry point to the cloud.


%prep 
%setup -q -n %{name}-%{version}

%build


%install
rm -rf %{buildroot}

python setup.py install --root=%{buildroot}

mkdir -p %{buildroot}/etc/init.d
install -m755 scripts/init/cocaine-tornado-proxy %{buildroot}/etc/init.d/cocaine-tornado-proxy
mkdir -p %{buildroot}/etc/cocaine
install -m644 scripts/init/cocaine-tornado-proxy.conf %{buildroot}/etc/cocaine/cocaine-tornado-proxy.conf


%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc README* LICENSE
%{python_sitelib}/*

%files -n cocaine-tools
%defattr(-,root,root,-)
%doc README* LICENSE
%{_bindir}/*

%files -n cocaine-tornado-proxy
%defattr(-,root,root,-)
%doc README* LICENSE
/etc/cocaine/cocaine-tornado-proxy.conf
/etc/init.d/cocaine-tornado-proxy


%changelog
* Thu Jul 27 2013 Arkady L. Shane <ashejn@russianfedora.ru> - 0.10.5.5-1
- initial build
