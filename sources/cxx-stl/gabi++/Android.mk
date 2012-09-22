LOCAL_PATH:= $(call my-dir)

include $(LOCAL_PATH)/sources.mk

ifneq ($(NDK_APP_USE_BITCODE),true)

ifeq (,$(GABIXX_FORCE_REBUILD))

  include $(CLEAR_VARS)
  LOCAL_MODULE:= gabi++_shared
  LOCAL_SRC_FILES:= libs/$(TARGET_ARCH_ABI)/lib$(LOCAL_MODULE).so
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(PREBUILT_SHARED_LIBRARY)

  include $(CLEAR_VARS)
  LOCAL_MODULE:= gabi++_static
  LOCAL_SRC_FILES:= libs/$(TARGET_ARCH_ABI)/lib$(LOCAL_MODULE).a
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(PREBUILT_STATIC_LIBRARY)

else # ! GABIXX_FORCE_REBUILD

  # Shared version of the library
  # Note that the module is named libgabi++_shared to avoid
  # any conflict with any potential system library named libgabi++
  #
  include $(CLEAR_VARS)
  LOCAL_MODULE:= libgabi++_shared
  LOCAL_CPP_EXTENSION := .cc
  LOCAL_SRC_FILES:= $(libgabi++_src_files)
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(BUILD_SHARED_LIBRARY)

  # And now the static version
  #
  include $(CLEAR_VARS)
  LOCAL_MODULE:= libgabi++_static
  LOCAL_SRC_FILES:= $(libgabi++_src_files)
  LOCAL_CPP_EXTENSION := .cc
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(BUILD_STATIC_LIBRARY)

endif # ! GABIXX_FORCE_REBUILD

else # NDK_APP_USE_BITCODE == true

# We only support static bitcode library, force stlport_static and
# stlport_shared to static library.

ifeq (,$(GABIXX_FORCE_REBUILD))

  include $(CLEAR_VARS)
  LOCAL_MODULE:= gabi++_shared
  LOCAL_SRC_FILES:= ../../android/pndk/llvm/lib/libgabi++_shared.a
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(PREBUILT_STATIC_LIBRARY)

  include $(CLEAR_VARS)
  LOCAL_MODULE:= gabi++_static
  LOCAL_SRC_FILES:= ../../android/pndk/llvm/lib/libgabi++_static.a
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(PREBUILT_STATIC_LIBRARY)

else # ! GABIXX_FORCE_REBUILD

  include $(CLEAR_VARS)
  LOCAL_MODULE:= libgabi++_shared
  LOCAL_CPP_EXTENSION := .cc
  LOCAL_SRC_FILES:= $(libgabi++_src_files)
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(BUILD_STATIC_LIBRARY)

  include $(CLEAR_VARS)
  LOCAL_MODULE:= libgabi++_static
  LOCAL_SRC_FILES:= $(libgabi++_src_files)
  LOCAL_CPP_EXTENSION := .cc
  LOCAL_EXPORT_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_C_INCLUDES := $(libgabi++_c_includes)
  LOCAL_CPP_FEATURES := rtti
  include $(BUILD_STATIC_LIBRARY)

endif # ! GABIXX_FORCE_REBUILD

endif # NDK_APP_USE_BITCODE == true
