#
# Copyright (C) 2015 The Android Open Source Project
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
import argparse
import inspect
import multiprocessing
import os
import subprocess
import sys


ALL_TOOLCHAINS = (
    'arm-linux-androideabi',
    'aarch64-linux-android',
    'mipsel-linux-android',
    'mips64el-linux-android',
    'x86',
    'x86_64',
)


ALL_ARCHITECTURES = (
    'arm',
    'arm64',
    'mips',
    'mips64',
    'x86',
    'x86_64',
)


def arch_to_toolchain(arch):
    return dict(zip(ALL_ARCHITECTURES, ALL_TOOLCHAINS))[arch]


def toolchain_to_arch(toolchain):
    return dict(zip(ALL_TOOLCHAINS, ALL_ARCHITECTURES))[toolchain]


def android_path(path=''):
    top = os.getenv('ANDROID_BUILD_TOP', '')
    return os.path.realpath(os.path.join(top, path))


def sysroot_path(toolchain):
    arch = toolchain_to_arch(toolchain)
    version = default_api_level(arch)

    prebuilt_ndk = 'prebuilts/ndk/current'
    sysroot_subpath = 'platforms/android-{}/arch-{}'.format(version, arch)
    return android_path(os.path.join(prebuilt_ndk, sysroot_subpath))


def ndk_path(path=''):
    return android_path(os.path.join('ndk', path))


def toolchain_path(path=''):
    return android_path(os.path.join('toolchain', path))


def default_api_level(arch):
    if '64' in arch:
        return 21
    else:
        return 9


def jobs_arg():
    return '-j{}'.format(multiprocessing.cpu_count() * 2)


def build(cmd, args):
    common_args = [
        '--verbose',
        '--package-dir={}'.format(args.package_dir),
    ]

    build_env = dict(os.environ)
    build_env['NDK_BUILDTOOLS_PATH'] = android_path('ndk/build/tools')
    build_env['ANDROID_NDK_ROOT'] = ndk_path()
    subprocess.check_call(cmd + common_args, env=build_env)


def get_default_package_dir():
    return android_path('out/ndk')


def get_default_host():
    if sys.platform in ('linux', 'linux2'):
        return 'linux'
    elif sys.platform == 'darwin':
        return 'darwin'
    else:
        raise RuntimeError('Unsupported host: {}'.format(sys.platform))


class ArgParser(argparse.ArgumentParser):
    def __init__(self):
        super(ArgParser, self).__init__()

        self.add_argument(
            '--host', choices=('darwin', 'linux', 'windows', 'windows64'),
            default=get_default_host(),
            help='Build binaries for given OS (e.g. linux).')
        self.add_argument(
            '--package-dir', help='Directory to place the packaged GCC.',
            default=get_default_package_dir())


def run(main_func, arg_parser=ArgParser):
    caller_filename = inspect.getouterframes(inspect.currentframe())[1][1]
    caller_dir = os.path.dirname(caller_filename)

    if 'ANDROID_BUILD_TOP' not in os.environ:
        top = os.path.join(os.path.dirname(caller_filename), '../..')
        os.environ['ANDROID_BUILD_TOP'] = os.path.realpath(top)

    os.chdir(caller_dir)

    args = arg_parser().parse_args()
    main_func(args)
