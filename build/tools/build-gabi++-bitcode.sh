#!/bin/sh
#
# Copyright (C) 2011 The Android Open Source Project
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
#  This shell script is used to rebuild the prebuilt GAbi++ binaries from
#  their sources. It requires a working NDK installation.
#

# include common function and variable definitions
. `dirname $0`/prebuilt-common.sh
. `dirname $0`/builder-funcs.sh

PROGRAM_PARAMETERS=""

PROGRAM_DESCRIPTION=\
"Rebuild the prebuilt GAbi++ bitcodes for the Android NDK.

This script is called when packaging a new NDK release. It will simply
rebuild the GAbi++ bitcode from sources.

This requires a temporary NDK installation containing platforms and
toolchain binaries for all target architectures.

By default, this will try with the current NDK directory, unless
you use the --ndk-dir=<path> option.

The output will be placed in appropriate sub-directories of
<ndk>/sources/android/pndk/llvm/lib, but you can override this with the --out-dir=<path>
option.
"

PACKAGE_DIR=
register_var_option "--package-dir=<path>" PACKAGE_DIR "Put prebuilt tarballs into <path>."

NDK_DIR=
register_var_option "--ndk-dir=<path>" NDK_DIR "Specify NDK root path for the build."

BUILD_DIR=
OPTION_BUILD_DIR=
register_var_option "--build-dir=<path>" OPTION_BUILD_DIR "Specify temporary build dir."

OUT_DIR=
register_var_option "--out-dir=<path>" OUT_DIR "Specify output directory directly."

ABIS="$PREBUILT_ABIS"
register_var_option "--abis=<list>" ABIS "Specify list of target ABIs."

NO_MAKEFILE=
register_var_option "--no-makefile" NO_MAKEFILE "Do not use makefile to speed-up build"

register_jobs_option

extract_parameters "$@"

# Handle NDK_DIR
if [ -z "$NDK_DIR" ] ; then
    NDK_DIR=$ANDROID_NDK_ROOT
    log "Auto-config: --ndk-dir=$NDK_DIR"
else
    if [ ! -d "$NDK_DIR" ] ; then
        echo "ERROR: NDK directory does not exists: $NDK_DIR"
        exit 1
    fi
fi

if [ -z "$OPTION_BUILD_DIR" ]; then
    BUILD_DIR=$NDK_TMPDIR/build-gabi++
else
    BUILD_DIR=$OPTION_BUILD_DIR
fi
mkdir -p "$BUILD_DIR"
fail_panic "Could not create build directory: $BUILD_DIR"

LLVM_LIB_DIR=sources/android/pndk/llvm/lib
DEVELOPMENT_ROOT=`dirname $NDK_DIR`/development/ndk

COMMON_CFLAGS="-emit-llvm -nostdlibinc \
              -I$DEVELOPMENT_ROOT/sources/android/pndk/include \
              -I$NDK_DIR/platforms/android-9/arch-arm/usr/include"

GABIXX_SRCDIR=$ANDROID_NDK_ROOT/$GABIXX_SUBDIR

GABIXX_CFLAGS="$COMMON_CFLAGS -fPIC -O2 -DANDROID -D__ANDROID__"
GABIXX_CFLAGS=$GABIXX_CFLAGS" -I$GABIXX_SRCDIR/include"
GABIXX_CXXFLAGS="-fuse-cxa-atexit -fno-exceptions -frtti"
GABIXX_LDFLAGS=

# List of sources to compile
GABIXX_SOURCES=$(cd $GABIXX_SRCDIR && ls src/*.cc)

# If the --no-makefile flag is not used, we're going to put all build
# commands in a temporary Makefile that we will be able to invoke with
# -j$NUM_JOBS to build stuff in parallel.
#
if [ -z "$NO_MAKEFILE" ]; then
    MAKEFILE=$BUILD_DIR/Makefile
else
    MAKEFILE=
fi

build_gabixx_libs ()
{
    local BUILDDIR="$1"
    local DSTDIR="$2"
    local SRC OBJ OBJECTS CFLAGS CXXFLAGS

    mkdir -p "$BUILDDIR"

    # If the output directory is not specified, use default location
    if [ -z "$DSTDIR" ]; then
        DSTDIR=$NDK_DIR/$LLVM_LIB_DIR
    fi

    mkdir -p "$DSTDIR"

    builder_begin_android_llvm "$BUILDDIR" "$MAKEFILE"

    builder_set_dstdir "$DSTDIR"

    builder_set_srcdir "$GABIXX_SRCDIR"
    builder_cflags "$GABIXX_CFLAGS"
    builder_cxxflags "$GABIXX_CXXFLAGS"
    builder_ldflags "$GABIXX_LDFLAGS"
    builder_sources $GABIXX_SOURCES

    rm -f $DSTDIR/libgabi++_static.a
    log "Building $DSTDIR/libgabi++_static.a"
    builder_static_library libgabi++_static

    builder_end
}

build_gabixx_libs "$BUILD_DIR"

# Both shared and static library using prebuilt bitcode
cp -f $NDK_DIR/$LLVM_LIB_DIR/libgabi++_static.a $NDK_DIR/$LLVM_LIB_DIR/libgabi++_shared.a

# If needed, package files into tarballs
if [ -n "$PACKAGE_DIR" ] ; then
    FILES="$LLVM_LIB_DIR/libgabi++_static.a $LLVM_LIB_DIR/libgabi++_shared.a"
    PACKAGE="$PACKAGE_DIR/gabixx-libs-bitcode.tar.bz2"
    log "Packaging: $PACKAGE"
    pack_archive "$PACKAGE" "$NDK_DIR" "$FILES"
    fail_panic "Could not package GAbi++ bitcode!"
    dump "Packaging: $PACKAGE"
fi

if [ -z "$OPTION_BUILD_DIR" ]; then
    log "Cleaning up..."
    rm -rf $BUILD_DIR
else
    log "Don't forget to cleanup: $BUILD_DIR"
fi

log "Done!"
