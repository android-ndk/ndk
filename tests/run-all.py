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
"""Runs all NDK tests."""
from __future__ import print_function

import argparse
import contextlib
import functools
import glob
import inspect
import multiprocessing
import os
import re
import shutil
import subprocess
import sys


DEV_NULL = open(os.devnull, 'wb')


THIS_DIR = os.path.dirname(os.path.realpath(__file__))
NDK_ROOT = os.path.realpath(os.path.join(THIS_DIR, '..'))


SUPPORTED_ABIS = (
    'armeabi',
    'armeabi-v7a',
    'arm64-v8a',
    'mips',
    'mips64',
    'x86',
    'x86_64',
)


# TODO(danalbert): How much time do we actually save by not running these?
LONG_TESTS = (
    'prebuild-stlport',
    'test-stlport',
    'test-gnustl-full',
    'test-stlport_shared-exception',
    'test-stlport_static-exception',
    'test-gnustl_shared-exception-full',
    'test-gnustl_static-exception-full',
    'test-googletest-full',
    'test-libc++-shared-full',
    'test-libc++-static-full',
)


@contextlib.contextmanager
def cd(path):
    curdir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(curdir)


def is_valid_platform_version(version_string):
    match = re.match(r'^android-(\d+)$', version_string)
    if not match:
        return False

    # We don't support anything before Gingerbread.
    version = int(match.group(1))
    return version >= 9


def android_platform_version(version_string):
    if is_valid_platform_version(version_string):
        return version_string
    else:
        raise argparse.ArgumentTypeError(
            'Platform version must match the format "android-VERSION", where '
            'VERSION >= 9.')


class ArgParser(argparse.ArgumentParser):
    def __init__(self):
        super(ArgParser, self).__init__(
            description=inspect.getdoc(sys.modules[__name__]))

        self.add_argument(
            '--abi', default=None, choices=SUPPORTED_ABIS,
            help=('Run tests against the specified ABI. Defaults to the '
                  'contents of APP_ABI in jni/Application.mk'))
        self.add_argument(
            '--platform', default=None, type=android_platform_version,
            help=('Run tests against the specified platform version. Defaults '
                  'to the contents of APP_PLATFORM in jni/Application.mk'))
        self.add_argument(
            '--show-commands', action='store_true',
            help='Show build commands for each test.')
        self.add_argument(
            '--suite', default=None,
            choices=('awk', 'build', 'device', 'samples'),
            help=('Run only the chosen test suite.'))

        self.add_argument(
            '--quick', action='store_true', help='Skip long running tests.')


def color_string(string, color):
    colors = {
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
    }
    end_color = '\033[0m'
    return colors[color] + string + end_color


class TestResult(object):
    def __init__(self, test_name, passed):
        self.passed = passed
        self.test_name = test_name

    def __repr__(self):
        return self.to_string(colored=False)

    def to_string(self, colored=False):
        raise NotImplementedError


class Failure(TestResult):
    def __init__(self, test_name, message):
        super(Failure, self).__init__(test_name, passed=False)
        self.message = message

    def to_string(self, colored=False):
        label = color_string('FAIL', 'red') if colored else 'FAIL'
        return '{} {}: {}'.format(label, self.test_name, self.message)


class Success(TestResult):
    def __init__(self, test_name):
        super(Success, self).__init__(test_name, passed=True)

    def to_string(self, colored=False):
        label = color_string('PASS', 'green') if colored else 'PASS'
        return '{} {}'.format(label, self.test_name)


class Skipped(TestResult):
    def __init__(self, test_name, reason):
        super(Skipped, self).__init__(test_name, passed=False)
        self.reason = reason

    def to_string(self, colored=False):
        label = color_string('SKIP', 'yellow') if colored else 'SKIP'
        return '{} {}: {}'.format(label, self.test_name, self.reason)


def run_awk_test_case(out_dir, test_name, script, test_case, golden_out_path):
    out_path = os.path.join(out_dir, os.path.basename(golden_out_path))

    with open(test_case, 'r') as test_in, open(out_path, 'w') as out_file:
        print('awk -f {} < {} > {}'.format(script, test_case, out_path))
        rc = subprocess.call(['awk', '-f', script], stdin=test_in,
                             stdout=out_file)
        if rc != 0:
            return Failure(test_name, 'awk failed')

    rc = subprocess.call(['cmp', out_path, golden_out_path], stdout=DEV_NULL,
                         stderr=DEV_NULL)
    if rc == 0:
        return Success(test_name)
    else:
        p = subprocess.Popen(['diff', '-buN', out_path, golden_out_path],
                             stdout=subprocess.PIPE, stderr=DEV_NULL)
        out, _ = p.communicate()
        if p.returncode != 0:
            raise RuntimeError('Could not generate diff')
        message = 'output does not match expected:\n\n' + out
        return Failure(test_name, message)


def run_awk_test(out_dir, test_dir):
    test_name = '{}.awk'.format(os.path.basename(test_dir))
    script = os.path.join(test_dir, test_name)
    if not os.path.isfile(script):
        return [Failure(test_name, 'missing test script: {}'.format(script))]
    results = []
    for test_case in glob.glob(os.path.join(test_dir, '*.in')):
        test_case = os.path.join(test_dir, test_case)
        golden_path = re.sub(r'\.in$', '.out', test_case)
        if not os.path.isfile(golden_path):
            results.append(Failure(test_name,
                                   'missing output: {}'.format(golden_path)))
        results.append(run_awk_test_case(out_dir, test_name, script, test_case,
                                         golden_path))
    return results


def get_jobs_arg():
    return '-j{}'.format(multiprocessing.cpu_count() * 2)


def prep_build_dir(src_dir, out_dir):
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(src_dir, out_dir)


def run_build_sh_test(test_name, build_dir, test_dir, build_flags):
    # TODO(danalbert): Figure out why we need the following block.
    # The following block was in the old test script, but the comment
    # seems to say the opposite of what it does.
    # if [ -f "$1/jni/Android.mk" -a -f "$1/jni/Application.mk" ] ; then
    #     # exclude jni/Android.mk with import-module because it needs
    #     # NDK_MODULE_PATH
    #     grep -q  "call import-module" "$1/jni/Android.mk"
    #     if [ $? != 0 ] ; then
    #         if (is_broken_build $1 || is_incompatible_abi $1) then
    #             return 0;
    #         fi
    #     fi
    # fi

    prep_build_dir(test_dir, build_dir)
    with cd(build_dir):
        build_cmd = ['sh', 'build.sh', get_jobs_arg()] + build_flags
        if subprocess.call(build_cmd) == 0:
            return Success(test_name)
        else:
            return Failure(test_name, 'build failed')


def test_is_disabled(test_dir, platform):
    disable_file = os.path.join(test_dir, 'BROKEN_BUILD')
    if os.path.isfile(disable_file):
        if os.stat(disable_file).st_size == 0:
            return True

        # This might look like clang-3.6 and gcc-3.6 would overlap (not a
        # problem today, but maybe when we hit clang-4.9), but clang is
        # actually written as clang3.6 (with no hypen), so toolchain_version
        # will end up being 'clang3.6'.
        toolchain = get_build_var(test_dir, 'TARGET_TOOLCHAIN')
        toolchain_version = toolchain.split('-')[-1]
        with open(disable_file) as f:
            contents = f.read()
        broken_configs = re.split(r'\s+', contents)
        if toolchain_version in broken_configs:
            return True
        if platform is not None and platform in broken_configs:
            return True
    return False


def get_build_var(test_dir, var_name):
    makefile = os.path.join(NDK_ROOT, 'build/core/build-local.mk')
    cmd = ['make', '--no-print-dir', '-f', makefile, '-C', test_dir,
           'DUMP_{}'.format(var_name)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    if p.returncode != 0:
        raise RuntimeError('Could not get build variable')
    return out.strip().split('\n')[-1]


def ndk_build(build_flags):
    ndk_build_path = os.path.join(NDK_ROOT, 'ndk-build')
    return subprocess.call([ndk_build_path, get_jobs_arg()] + build_flags)


def expand_app_abi(abi):
    all32 = ('armeabi', 'armeabi-v7a', 'mips', 'x86')
    all64 = ('arm64-v8a', 'mips64', 'x86_64')
    all_abis = all32 + all64
    if abi == 'all':
        return all_abis
    elif abi == 'all32':
        return all32
    elif abi == 'all64':
        return all64
    return [abi]


def run_ndk_build_test(test_name, build_dir, test_dir, build_flags, abi,
                       platform):
    if test_is_disabled(test_dir, platform):
        return Skipped(test_name, 'disabled')
    if abi is not None:
        app_abi = get_build_var(test_dir, 'APP_ABI')
        supported_abis = expand_app_abi(app_abi)
        if abi not in supported_abis:
            return Skipped(test_name, 'incompatible ABI (requires {})'.format(
                ', '.join(supported_abis)))

    prep_build_dir(test_dir, build_dir)
    with cd(build_dir):
        rc = ndk_build(build_flags)
    expect_failure = os.path.isfile(
        os.path.join(test_dir, 'BUILD_SHOULD_FAIL'))
    if rc == 0 and expect_failure:
        return Failure(test_name, 'build should have failed')
    elif rc != 0 and not expect_failure:
        return Failure(test_name, 'build failed')
    return Success(test_name)


def run_build_test(out_dir, test_dir, build_flags, abi, platform):
    test_name = os.path.basename(test_dir)
    print('Running build test: {}'.format(test_name))

    build_dir = os.path.join(out_dir, test_name)
    if os.path.isfile(os.path.join(test_dir, 'build.sh')):
        return [run_build_sh_test(test_name, build_dir, test_dir, build_flags)]
    else:
        return [run_ndk_build_test(test_name, build_dir, test_dir, build_flags,
                                   abi, platform)]


def adb_push(src, dst):
    subprocess.check_call(['adb', 'push', src, dst], stdout=DEV_NULL,
                          stderr=DEV_NULL)


def adb_shell(command):
    # Work around the fact that adb doesn't return shell exit status.
    p = subprocess.Popen(['adb', 'shell', command + '; echo $?'],
                         stdout=subprocess.PIPE)
    out, _ = p.communicate()
    if p.returncode != 0:
        raise RuntimeError('adb shell failed')

    out = re.split(r'[\r\n]+', out)
    if out[-1] == '':
        # Splitting 'foo\n' will return ['foo', '']. Lose the last element.
        out = out[:-1]
    result = int(out[-1])
    out = out[:-1]
    return result, out


def adb_get_prop(prop_name):
    result, output = adb_shell('getprop {}'.format(prop_name))
    if result != 0:
        raise RuntimeError('getprop failed:\n' + '\n'.join(output))
    if len(output) != 1:
        raise RuntimeError('Too many lines in getprop output:\n' +
                           '\n'.join(output))
    value = output[0]
    if not value.strip():
        return None
    return value


def copy_test_to_device(build_dir, device_dir, abi):
    abi_dir = os.path.join(build_dir, 'libs', abi)
    if not os.path.isdir(abi_dir):
        raise RuntimeError('No libraries for {}'.format(abi))

    test_cases = []
    for test_file in os.listdir(abi_dir):
        if test_file in ('gdbserver', 'gdb.setup'):
            continue

        if not test_file.endswith('.so'):
            test_cases.append(test_file)

        # TODO(danalbert): Libs with the same name will clobber each other.
        # This was the case with the old shell based script too. I'm trying not
        # to change too much in the translation.
        lib_path = os.path.join(abi_dir, test_file)
        adb_push(lib_path, device_dir)

        # TODO(danalbert): Sync data.
        # The libc++ tests contain a DATA file that lists test names and their
        # dependencies on file system data. These files need to be copied to
        # the device.

    if len(test_cases) == 0:
        raise RuntimeError('Could not find any test executables.')

    return test_cases


def run_is_disabled(test_case, test_dir):
    """Returns True if the test case is disabled.

    There is no strict format for the BROKEN_RUN file; test cases are disabled
    if their basename appears anywhere in the file.
    """
    disable_file = os.path.join(test_dir, 'BROKEN_RUN')
    if not os.path.exists(disable_file):
        return False
    return subprocess.call(['grep', '-qw', test_case, disable_file]) == 0


def run_device_test(out_dir, test_dir, build_flags, abi, platform):
    test_name = os.path.basename(test_dir)
    build_dir = os.path.join(out_dir, test_name)
    build_result = run_ndk_build_test(test_name, build_dir, test_dir,
                                      build_flags, abi, platform)
    if not build_result.passed:
        return [build_result]

    device_dir = os.path.join('/data/local/tmp/ndk-tests', test_name)

    result, out = adb_shell('mkdir -p {}'.format(device_dir))
    if result != 0:
        raise RuntimeError('mkdir failed:\n' + '\n'.join(out))

    results = []
    try:
        test_cases = copy_test_to_device(build_dir, device_dir, abi)
        for case in test_cases:
            case_name = '.'.join([test_name, case])
            if run_is_disabled(case, test_dir):
                results.append(Skipped(case_name, 'run disabled'))
                continue

            cmd = 'cd {} && LD_LIBRARY_PATH={} ./{}'.format(
                device_dir, device_dir, case)
            result, out = adb_shell(cmd)
            if result == 0:
                results.append(Success(case_name))
            else:
                results.append(Failure(case_name, '\n'.join(out)))
        return results
    finally:
        adb_shell('rm -rf {}'.format(device_dir))


def run_tests(out_dir, test_dir, test_func):
    results = []
    for dentry in os.listdir(test_dir):
        path = os.path.join(test_dir, dentry)
        if os.path.isdir(path):
            try:
                results.extend(test_func(out_dir, path))
            except RuntimeError as ex:
                results.append(Failure(os.path.basename(dentry), ex))
    return results


def get_test_device():
    if subprocess.call(['which', 'adb'], stdout=DEV_NULL) != 0:
        raise RuntimeError('Could not find adb.')

    p = subprocess.Popen(['adb', 'devices'], stdout=subprocess.PIPE)
    out, _ = p.communicate()
    if p.returncode != 0:
        raise RuntimeError('Failed to get list of devices from adb.')

    # The first line of `adb devices` just says "List of attached devices", so
    # skip that.
    devices = []
    for line in out.split('\n')[1:]:
        if not line.strip():
            continue
        if 'offline' in line:
            continue

        serial, _ = re.split(r'\s+', line, maxsplit=1)
        devices.append(serial)

    if len(devices) == 0:
        raise RuntimeError('No devices detected.')

    device = os.getenv('ANDROID_SERIAL')
    if device is None and len(devices) == 1:
        device = devices[0]

    if device is not None and device not in devices:
        raise RuntimeError('Device {} is not available.'.format(device))

    # TODO(danalbert): Handle running against multiple devices in one pass.
    if len(devices) > 1 and device is None:
        raise RuntimeError('Multiple devices detected and ANDROID_SERIAL not '
                           'set. Cannot continue.')

    return device


def get_device_abis():
    abis = [adb_get_prop('ro.product.cpu.abi')]
    abi2 = adb_get_prop('ro.product.cpu.abi2')
    if abi2 is not None:
        abis.append(abi2)
    return abis


def check_adb_works_or_die(abi):
    # TODO(danalbert): Check that we can do anything with the device.
    try:
        device = get_test_device()
    except RuntimeError as ex:
        sys.exit('Error: {}'.format(ex))

    if abi is not None and abi not in get_device_abis():
        sys.exit('The test device ({}) does not support the requested ABI '
                 '({})'.format(device, abi))


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    args = ArgParser().parse_args()
    ndk_build_flags = []
    if args.abi is not None:
        ndk_build_flags.append('APP_ABI={}'.format(args.abi))
    if args.platform is not None:
        ndk_build_flags.append('APP_PLATFORM={}'.format(args.platform))
    if args.show_commands:
        ndk_build_flags.append('V=1')

    if not os.path.exists(os.path.join('../build/tools/prebuilt-common.sh')):
        sys.exit('Error: Not run from a valid NDK.')

    out_dir = 'out'
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)

    my_run_build_test = functools.partial(run_build_test,
                                          build_flags=ndk_build_flags,
                                          abi=args.abi,
                                          platform=args.platform)

    my_run_device_test = functools.partial(run_device_test,
                                           build_flags=ndk_build_flags,
                                           abi=args.abi,
                                           platform=args.platform)

    suites = ['awk', 'build', 'device', 'samples']
    if args.suite:
        suites = [args.suite]

    # Do this early so we find any device issues now rather than after we've
    # run all the build tests.
    if 'device' in suites:
        check_adb_works_or_die(args.abi)

    os.environ['ANDROID_SERIAL'] = get_test_device()

    results = {suite: [] for suite in suites}
    if 'awk' in suites:
        results['awk'] = run_tests(out_dir, 'awk', run_awk_test)
    if 'build' in suites:
        results['build'] = run_tests(out_dir, 'build', my_run_build_test)
    if 'samples' in suites:
        results['samples'] = run_tests(out_dir, '../samples',
                                       my_run_build_test)
    if 'device' in suites:
        results['device'] = run_tests(out_dir, 'device', my_run_device_test)

    use_color = sys.stdin.isatty()
    for suite, test_results in results.items():
        print('{}:'.format(suite))
        for result in test_results:
            if not result.passed:
                print('\t{}'.format(result.to_string(colored=use_color)))


if __name__ == '__main__':
    main()
