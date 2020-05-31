#!/bin/bash

EXTRA_CFLAGS="-Werror"

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
            EXTRA_CFLAGS="${EXTRA_CFLAGS} -m32";
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
        echo "Python version: $(/usr/bin/python -V 2>&1)";
	;;
    "osx")
        python --version
        brew update
        brew install cunit
        pip3 install scipy
        pip install six
	;;
esac

./configure --extra-cflags="${EXTRA_CFLAGS}" &&
    make &&
    make test &&
    if [[ "$TRAVIS_CPU_ARCH" == "arm64" ]]; then
        sudo python3 t/run-fio-tests.py --skip 6 1007 1008 --debug -p 1010:"--skip 15 16 17 18 19 20"
    else
        sudo python3 t/run-fio-tests.py --skip 6 1007 1008 --debug --run-only 1011
    fi
