#!/usr/bin/env python
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
"""Verifies that the build is sane.

Cleans old build artifacts, configures the required environment, determines
build goals, and invokes the build scripts.
"""
import os
import platform
import subprocess
import sys


def invoke_build(script, args=None):
    if args is None:
        args = []
    subprocess.check_call([os.path.join('build/tools', script)] + args)


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    # Set ANDROID_BUILD_TOP.
    if 'ANDROID_BUILD_TOP' not in os.environ:
        os.environ['ANDROID_BUILD_TOP'] = os.path.realpath('..')
    build_top = os.getenv('ANDROID_BUILD_TOP')

    # Set default --package-dir
    DEFAULT_OUT_DIR = os.path.join(build_top, 'out/ndk')
    package_dir = os.path.realpath(os.getenv('DIST_DIR', DEFAULT_OUT_DIR))
    package_dir_arg = '--package-dir={}'.format(package_dir)

    # Deal with --systems
    system = None
    for arg in sys.argv[1:]:
        if arg.startswith('--systems='):
            system = arg.partition('=')[2]

    # Run dev-cleanup
    invoke_build('dev-cleanup.sh')

    # Configure common args
    toolchain_path = os.path.join(build_top, 'toolchain')
    common_args = [toolchain_path, '--verbose', '--try-64', package_dir_arg]

    # Build
    if system == 'windows' or platform.system() == 'Darwin':
        ndk_dir_arg = '--ndk-dir={}'.format(os.getcwd())
        invoke_build('build-host-prebuilts.sh',
                     common_args + [ndk_dir_arg] + sys.argv[1:])
    else:
        invoke_build('rebuild-all-prebuilt.sh', common_args + sys.argv[1:])


if __name__ == '__main__':
    main()
