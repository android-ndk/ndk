#!/usr/bin/env python
#
# Copyright (C) 2016 The Android Open Source Project
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
"""Runs the test suite over a set of devices."""
from __future__ import print_function

import argparse
import distutils.spawn
import os
import re
import shutil
import site
import subprocess
import sys


THIS_DIR = os.path.realpath(os.path.dirname(__file__))


class Device(object):
    def __init__(self, serial, name, version, abis):
        self.serial = serial
        self.name = name
        self.version = version
        self.abis = abis
        self.is_emulator = False  # TODO(danalbert): Identify these.

    def __str__(self):
        return 'android-{} {} {}'.format(self.version, self.name, self.serial)


class DeviceFleet(object):
    def __init__(self):
        self.devices = {
            10: {
                'armeabi': None,
                'armeabi-v7a': None,
                'armeabi-v7a-hard': None,
            },
            16: {
                'armeabi': None,
                'armeabi-v7a': None,
                'armeabi-v7a-hard': None,
                'mips': None,
                'x86': None,
            },
            23: {
                'armeabi': None,
                'armeabi-v7a': None,
                'armeabi-v7a-hard': None,
                'arm64-v8a': None,
                'mips': None,
                'mips64': None,
                'x86': None,
                'x86_64': None,
            },
        }

    def add_device(self, device):
        if device.version not in self.devices:
            print('Ignoring device for unwanted API level: {}'.format(device))
            return

        same_version = self.devices[device.version]
        for abi, current_device in same_version.iteritems():
            # This device can't fulfill this ABI.
            if abi not in device.abis:
                continue

            # Anything is better than nothing.
            if current_device is None:
                self.devices[device.version][abi] = device
                continue

            # The emulator images have actually been changed over time, so the
            # devices are more trustworthy.
            if current_device.is_emulator and not device.is_emulator:
                self.devices[device.version][abi] = device

    def get_device(self, version, abi):
        return self.devices[version][abi]

    def get_missing(self):
        missing = []
        for version, abis in self.devices.iteritems():
            for abi, device in abis.iteritems():
                if device is None:
                    missing.append('android-{} {}'.format(version, abi))
        return missing

    def get_versions(self):
        return self.devices.keys()

    def get_abis(self, version):
        return self.devices[version].keys()


def get_device_abis(properties):
    # 64-bit devices list their ABIs differently than 32-bit devices. Check all
    # the possible places for stashing ABI info and merge them.
    abi_properties = [
        'ro.product.cpu.abi',
        'ro.product.cpu.abi2',
        'ro.product.cpu.abilist',
    ]
    abis = set()
    for abi_prop in abi_properties:
        if abi_prop in properties:
            abis.update(properties[abi_prop].split(','))

    if 'armeabi-v7a' in abis:
        abis.add('armeabi-v7a-hard')
    return sorted(list(abis))


def get_device_details(serial):
    import adb  # pylint: disable=import-error
    props = adb.get_device(serial).get_props()
    name = props['ro.product.name']
    version = int(props['ro.build.version.sdk'])
    supported_abis = get_device_abis(props)
    return Device(serial, name, version, supported_abis)


def find_devices():
    """Detects connected devices and returns a set for testing.

    We get a list of devices by scanning the output of `adb devices`. We want
    to run the tests for the cross product of the following configurations:

    ABIs: {armeabi, armeabi-v7a, armeabi-v7a-hard, arm64-v8a, mips, mips64,
           x86, x86_64}
    Platform versions: {android-10, android-16, android-21}
    Toolchains: {clang, gcc}

    Note that not all ABIs are available for every platform version. There are
    no 64-bit ABIs before android-21, and there were no MIPS ABIs for
    android-10.
    """
    if distutils.spawn.find_executable('adb') is None:
        raise RuntimeError('Could not find adb.')

    # We could get the device name from `adb devices -l`, but we need to
    # getprop to find other details anyway, and older devices don't report
    # their names properly (nakasi on android-16, for example).
    p = subprocess.Popen(['adb', 'devices'], stdout=subprocess.PIPE)
    out, _ = p.communicate()
    if p.returncode != 0:
        raise RuntimeError('Failed to get list of devices from adb.')

    # The first line of `adb devices` just says "List of attached devices", so
    # skip that.
    fleet = DeviceFleet()
    for line in out.split('\n')[1:]:
        if not line.strip():
            continue

        serial, _ = re.split(r'\s+', line, maxsplit=1)

        if 'offline' in line:
            print('Ignoring offline device: ' + serial)
            continue
        if 'unauthorized' in line:
            print('Ignoring unauthorized device: ' + serial)
            continue

        device = get_device_details(serial)
        print('Found device {}'.format(device))
        fleet.add_device(device)

    return fleet


def run_tests(ndk, device, abi, toolchain, log_dir, extra_args):
    print('Running {} {} tests for {}... '.format(toolchain, abi, device),
          end='')
    sys.stdout.flush()

    env = dict(os.environ)
    env['ANDROID_SERIAL'] = device.serial
    env['NDK'] = ndk

    abi_arg = '--abi={}'.format(abi)
    toolchain_arg = '--toolchain={}'.format(toolchain)
    toolchain_name = 'gcc' if toolchain == '4.9' else toolchain
    log_file_name = '{}-{}-{}.log'.format(toolchain_name, abi, device.version)
    with open(os.path.join(log_dir, log_file_name), 'w') as log_file:
        args = ['python', 'tests/run-all.py', abi_arg, toolchain_arg]
        args.extend(extra_args)
        rc = subprocess.call(args, env=env, stdout=log_file,
                             stderr=subprocess.STDOUT)
        print('PASS' if rc == 0 else 'FAIL')
        return rc == 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'ndk', metavar='NDK', type=os.path.realpath, help='NDK to validate.')
    parser.add_argument(
        '--log-dir', type=os.path.realpath, default='test-logs',
        help='Directory to store test logs.')

    return parser.parse_known_args()


def main():
    args, run_all_args = parse_args()

    os.chdir(THIS_DIR)

    # We need to do this here rather than at the top because we load the module
    # from a path that is given on the command line. We load it from the NDK
    # given on the command line so this script can be run even without a full
    # platform checkout.
    site.addsitedir(os.path.join(THIS_DIR, '../development/python-packages'))

    ndk_build_path = os.path.join(args.ndk, 'ndk-build')
    if os.name == 'nt':
        ndk_build_path += '.cmd'
    if not os.path.exists(ndk_build_path):
        sys.exit(ndk_build_path + ' does not exist.')

    fleet = find_devices()
    missing_configs = fleet.get_missing()
    if len(missing_configs):
        print('Missing configurations: {}'.format(', '.join(missing_configs)))

    if os.path.exists(args.log_dir):
        shutil.rmtree(args.log_dir)
    os.makedirs(args.log_dir)

    # Note that we are duplicating some testing here.
    #
    # * The awk tests only need to be run once because they do not vary by
    #   configuration.
    # * The build tests only vary per-device by the PIE configuration, so we
    #   only need to run them twice per ABI/toolchain.
    # * The build tests are already run as a part of the build process.
    #
    # For local testing, it is probably desirable to pass `--suite device` to
    # speed things up.
    results = []
    good = True
    for version in fleet.get_versions():
        for abi in fleet.get_abis(version):
            device = fleet.get_device(version, abi)
            for toolchain in ('clang', '4.9'):
                if device is None:
                    results.append('android-{} {} {}: {}'.format(
                        version, abi, toolchain, 'SKIP'))
                    continue

                result = run_tests(
                    args.ndk, device, abi, toolchain, args.log_dir,
                    run_all_args)
                results.append('android-{} {} {}: {}'.format(
                    version, abi, toolchain, 'PASS' if result else 'FAIL'))
                if not result:
                    good = False

    print('\n'.join(results))
    sys.exit(not good)


if __name__ == '__main__':
    main()
