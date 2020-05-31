#!/bin/bash

case "$TRAVIS_OS_NAME" in
    "linux")
	# Architecture-dependent packages.
	pkgs=(
	    libaio-dev
	    libcunit1
	    libcunit1-dev
	    libgoogle-perftools4
	    libibverbs-dev
	    libiscsi-dev
	    libnuma-dev
	    librbd-dev
	    librdmacm-dev
	    libz-dev
	);
	if [[ "$BUILD_ARCH" == "x86" ]]; then
	    pkgs=("${pkgs[@]/%/:i386}");
	    pkgs+=(gcc-multilib);
	else
	    pkgs+=(glusterfs-common);
	fi;
	# Architecture-independent packages.
	pkgs+=(
	    python3-six
	    python3-scipy
	);
	sudo apt-get -qq update;
	sudo apt-get install --no-install-recommends -qq -y "${pkgs[@]}";
	if sudo apt-get install --no-install-recommends -qq -y "python3"; then
	    sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 50
	else
	    sudo apt-get install --no-install-recommends -qq -y "python2";
	fi;
	;;
    "osx")
	brew update
	brew install cunit
	pip3 install scipy
	pip install six
	;;
esac

echo "Python version: $(/usr/bin/python -V 2>&1)";
