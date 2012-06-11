#!/bin/sh
#
# Copyright (C) 2012 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Rebuild the host GCC toolchain binaries from sources.
#
# NOTE: this script does not rebuild gdb, see build-host-gdb.sh for this.
#

# include common function and variable definitions
NDK_BUILDTOOLS_PATH="$(dirname $0)"
. "$NDK_BUILDTOOLS_PATH/prebuilt-common.sh"
. "$NDK_BUILDTOOLS_PATH/common-build-host-funcs.sh"

PROGRAM_PARAMETERS=""
PROGRAM_DESCRIPTION="\
This program is used to rebuild one or more NDK gdb client programs from
sources. To use it, you will need a working set of toolchain sources, like
thos downloaded with download-toolchain-sources.sh., then pass the
corresponding directory with the --toolchain-src-dir=<path> option.

By default, the script rebuilds GDB for you host system [$HOST_TAG],
but you can use --systems=<tag1>,<tag2>,.. to ask binaries that can run on
several distinct systems. Each <tag> value in the list can be one of the
following:

   linux-x86
   linux-x86_64
   windows
   windows-x86  (equivalent to 'windows')
   windows-x86_64
   darwin-x86
   darwin-x86_64

For example, here's how to rebuild the ARM toolchains on Linux
for four different systems:

  $PROGNAME --toolchain-src-dir=/path/to/toolchain/src \
    --systems=linux-x86,linux-x86_64,windows,windows-x86_64 \
    arm-linux-androideabi-4.4.3 \
    arm-linux-androideabi-4.6
"

TOOLCHAIN_SRC_DIR=
register_var_option "--toolchain-src-dir=<path>" TOOLCHAIN_SRC_DIR "Select toolchain source directory"

GDB_VERSION="6.6 7.1.x 7.3.x"
register_var_option "--gdb-version=<version>" GDB_VERSION "Select GDB version(s)."

NDK_DIR=$ANDROID_NDK_ROOT
register_var_option "--ndk-dir=<path>" NDK_DIR "Select NDK install directory."

PACKAGE_DIR=
register_var_option "--package-dir=<path>" PACKAGE_DIR "Package prebuilt tarballs into directory."

ARCHS=$DEFAULT_ARCHS
register_var_option "--arch=<list>" ARCHS "Build GDB client for these CPU architectures."

bh_register_options

register_jobs_option

extract_parameters "$@"

if [ -n "$PARAMETERS" ]; then
    panic "This script doesn't take parameters, only options. See --help"
fi

if [ -z "$TOOLCHAIN_SRC_DIR" ]; then
    panic "Please use --toolchain-src-dir=<path> to select toolchain source directory."
fi

BH_HOST_SYSTEMS=$(commas_to_spaces $BH_HOST_SYSTEMS)

# Sanity check for all GDB versions
for VERSION in $(commas_to_spaces $GDB_VERSION); do
    GDB_SRCDIR=$TOOLCHAIN_SRC_DIR/gdb/gdb-$VERSION
    if [ ! -d "$GDB_SRCDIR" ]; then
        panic "Missing source directory: $GDB_SRCDIR"
    fi
done

bh_setup_build_dir

# Sanity check that we have the right compilers for all hosts
for SYSTEM in $BH_HOST_SYSTEMS; do
    bh_setup_build_for_host $SYSTEM
done

# Return the build install directory of a given GDB version
# $1: host system tag
# $2: target system tag
# $3: gdb version
gdb_build_install_dir ()
{
    echo "$BH_BUILD_DIR/install/$1/gdb-$(bh_tag_to_arch $2)-$3"
}

# Same as gdb_build_install_dir, but for the final NDK installation
# directory.
gdb_ndk_install_dir ()
{
    echo "$NDK_DIR/prebuilt/$1/gdb-$(bh_tag_to_arch $2)-$3"
}

# $1: host system tag
# $2: target tag
# $3: gdb version
build_host_gdb ()
{
    local SRCDIR=$TOOLCHAIN_SRC_DIR/gdb/gdb-$3
    local BUILDDIR=$BH_BUILD_DIR/build-gdb-$1-$2-$3
    local INSTALLDIR=$(gdb_build_install_dir $1 $2 $3)
    local ARGS TEXT

    if [ ! -f "$SRCDIR/configure" ]; then
        panic "Missing configure script in $SRCDIR"
    fi

    bh_set_target_tag $2

    ARGS=" --prefix=$INSTALLDIR"
    ARGS=$ARGS" --disable-shared"
    ARGS=$ARGS" --build=$BH_BUILD_CONFIG"
    ARGS=$ARGS" --host=$BH_HOST_CONFIG"
    ARGS=$ARGS" --target=$(bh_tag_to_config_triplet $2)"
    ARGS=$ARGS" --disable-werror"
    ARGS=$ARGS" --disable-nls"
    ARGS=$ARGS" --disable-docs"

    TEXT="$(bh_host_text) gdb-$BH_TARGET_ARCH-$3:"

    mkdir -p "$BUILDDIR" && rm -rf "$BUILDDIR"/* &&
    cd "$BUILDDIR" &&
    bh_setup_host_env &&
    dump "$TEXT Building"
    run2 "$SRCDIR"/configure $ARGS &&
    run2 make -j$NUM_JOBS &&
    run2 make -j$NUM_JOBS install
}

need_build_host_gdb ()
{
    bh_stamps_do host-gdb-$1-$2-$3 build_host_gdb $1 $2 $3
}

# Install host GDB binaries and support files to the NDK install dir.
# $1: host tag
# $2: target tag
# $3: gdb version
install_host_gdb ()
{
    local SRCDIR="$(gdb_build_install_dir $1 $2 $3)"
    local DSTDIR="$(gdb_ndk_install_dir $1 $2 $3)"

    need_build_host_gdb $1 $2 $3

    bh_set_target_tag $2

    dump "$(bh_host_text) gdb-$BH_TARGET_ARCH-$3: Installing"
    run copy_directory "$SRCDIR/bin" "$DSTDIR/bin"
    if [ -d "$SRCDIR/share/gdb" ]; then
        run copy_directory "$SRCDIR/share/gdb" "$DSTDIR/share/gdb"
    fi
}

GDB_VERSION=$(commas_to_spaces $GDB_VERSION)
ARCHS=$(commas_to_spaces $ARCHS)

# Let's build this
for SYSTEM in $BH_HOST_SYSTEMS; do
    bh_setup_build_for_host $SYSTEM
    for ARCH in $ARCHS; do
        for VERSION in $GDB_VERSION; do
            install_host_gdb $SYSTEM android-$ARCH $VERSION
        done
    done
done

# XXX: TODO PACKAGING
