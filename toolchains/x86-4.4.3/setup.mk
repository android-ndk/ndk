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

# this file is used to prepare the NDK to build with the x86-4.4.3
# toolchain any number of source files
#
# its purpose is to define (or re-define) templates used to build
# various sources into target object files, libraries or executables.
#
# Note that this file may end up being parsed several times in future
# revisions of the NDK.
#

TOOLCHAIN_NAME   := x86-4.4.3
TOOLCHAIN_PREFIX := $(TOOLCHAIN_PREBUILT_ROOT)/bin/i686-android-linux-

TARGET_CFLAGS := \
    -D__ANDROID__ \
    -mbionic \
    -I$(SYSROOT)/usr/include \
    -march=atom -mstackrealign -DUSE_SSSE3 -DUSE_SSE2 -mfpmath=sse \
    -Ulinux -m32 -fPIC \
    -ffunction-sections \
    -funwind-tables \
    -fno-short-enums

# Add and LDFLAGS for the target here
# TARGET_LDFLAGS :=

# Fix this after ssp.c is fixed for x86
# TARGET_CFLAGS += -fstack-protector

TARGET_x86_release_CFLAGS :=  -O2 \
                              -fomit-frame-pointer \
                              -fstrict-aliasing    \
                              -funswitch-loops     \
                              -finline-limit=300

# When building for debug, compile everything as x86.
TARGET_x86_debug_CFLAGS := $(TARGET_x86_release_CFLAGS) \
                           -fno-omit-frame-pointer \
                           -fno-strict-aliasing

# This function will be called to determine the target CFLAGS used to build
# a C or Assembler source file, based on its tags.
#
TARGET-process-src-files-tags = \
$(eval __debug_sources := $(call get-src-files-with-tag,debug)) \
$(eval __release_sources := $(call get-src-files-without-tag,debug)) \
$(call set-src-files-target-cflags, $(__debug_sources), $(TARGET_x86_debug_CFLAGS)) \
$(call set-src-files-target-cflags, $(__release_sources),$(TARGET_x86_release_CFLAGS)) \
$(call set-src-files-text,$(LOCAL_SRC_FILES),x86$(space)$(space)) \

# The ABI-specific sub-directory that the SDK tools recognize for
# this toolchain's generated binaries
TARGET_ABI_SUBDIR := x86


#
# We need to add -lsupc++ to the final link command to make exceptions
# and RTTI work properly (when -fexceptions and -frtti are used).
#
# Normally, the toolchain should be configured to do that automatically,
# this will be debugged later.
#

define cmd-build-shared-library
$(TARGET_CXX) \
    -nostdlib -Wl,-soname,$(notdir $@) \
    -Wl,-shared,-Bsymbolic \
    --sysroot=$(call host-path,$(SYSROOT)) \
    $(call host-path, $(TARGET_CRTBEGIN_SO_O)) \
    $(call host-path, $(PRIVATE_OBJECTS)) \
    $(call link-whole-archives,$(PRIVATE_WHOLE_STATIC_LIBRARIES)) \
    $(call host-path,\
        $(PRIVATE_STATIC_LIBRARIES) \
        $(PRIVATE_SHARED_LIBRARIES)) \
    $(PRIVATE_LDFLAGS) \
    $(PRIVATE_LDLIBS) \
    -lsupc++ -lgcc \
    $(call host-path, $(TARGET_CRTEND_SO_O)) \
    -o $(call host-path,$@)
endef

define cmd-build-executable
$(TARGET_CXX) \
    -nostdlib -Bdynamic \
    -Wl,-dynamic-linker,/system/bin/linker \
    -Wl,--gc-sections \
    -Wl,-z,nocopyreloc \
    --sysroot=$(call host-path,$(SYSROOT)) \
    $(call host-path, $(TARGET_CRTBEGIN_DYNAMIC_O)) \
    $(call host-path, $(PRIVATE_OBJECTS)) \
    $(call link-whole-archives,$(PRIVATE_WHOLE_STATIC_LIBRARIES)) \
    $(call host-path,\
        $(PRIVATE_STATIC_LIBRARIES) \
        $(PRIVATE_SHARED_LIBRARIES)) \
    $(PRIVATE_LDFLAGS) \
    $(PRIVATE_LDLIBS) \
    -lsupc++ -lgcc \
    $(call host-path, $(TARGET_CRTEND_O)) \
    -o $(call host-path,$@)
endef
