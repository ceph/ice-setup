%if 0%{?rhel} > 6
%global run_check 1
%else
# pytest is unavailable in the RHEL 6 Ceph buildroots.
# https://bugzilla.redhat.com/1184638
%global run_check 0
%endif

Name:           ice_setup
Version:        0.3.0
Release:        1%{?dist}
Summary:        Red Hat Ceph Storage setup tool
Group:          System Environment/Base
License:        MIT
URL:            https://github.com/ceph/ice-setup
# Generate this tarball by:
# 1. git clone ice-setup.git
# 2. cd ice-setup
# 3. git checkout <the version you want>
# 4. python setup.py sdist
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python-devel
BuildRequires:  python-setuptools
%if 0%{?run_check}
BuildRequires:  pytest
%endif # run_check

%description
A standalone setup script to install and configure different services for Ceph
like Calamari, ceph-deploy and package repositories.

%prep
%setup -q

%build
%{__python} setup.py build

%install
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

%check
%if 0%{?run_check}
rm -r build
%{__python} setup.py test
%endif # run_check

%files
%{_bindir}/%{name}
%{python_sitelib}/*

%changelog
