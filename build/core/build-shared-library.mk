# Copyright (C) 2009 The Android Open Source Project
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

# this file is included from Android.mk files to build a target-specific
# shared library
#

LOCAL_BUILD_SCRIPT := BUILD_SHARED_LIBRARY
LOCAL_MAKEFILE     := $(local-makefile)

$(call check-defined-LOCAL_MODULE,$(LOCAL_BUILD_SCRIPT))
$(call check-LOCAL_MODULE,$(LOCAL_MAKEFILE))
$(call check-LOCAL_MODULE_FILENAME)

# we are building target objects
my := TARGET_

ifeq ($(TARGET_ARCH_ABI),llvm)
$(call handle-module-filename,lib,.bc)
else
$(call handle-module-filename,lib,.so)
endif
$(call handle-module-built)

LOCAL_MODULE_CLASS := SHARED_LIBRARY
include $(BUILD_SYSTEM)/build-module.mk
