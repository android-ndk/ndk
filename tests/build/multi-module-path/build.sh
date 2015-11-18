#!/bin/sh

echo "\$0=$0"
cd `dirname $0`
echo "PWD=`pwd`"
export NDK_MODULE_PATH=`pwd`/path1:`pwd`/path2
$NDK/build/ndk-build "$@"
if [ $? != 0 ]; then
    echo "ERROR: Can't build test program!"
    exit 1
fi
