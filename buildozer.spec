[app]

# (str) Title of your application
title = BT Downloader

# (str) Package name
package.name = btdownloader

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,so

# (list) List of directory to exclude
source.exclude_dirs = tests, bin, recipes

# (version) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# libtorrent/boost 使用 python-for-android 上游 recipe（CI pin 到 v2024.01.21）
requirements = python3, kivy, android, openssl, libtorrent

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) List of supported Android permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (str) Android arch to build for
android.archs = arm64-v8a

# (str) Android NDK version
android.ndk = 25b

# (str) Android SDK version
android.sdk = 25.2.9519653

# (str) Android API
android.api = 33

# (str) Android minimum API
android.minapi = 24

# (bool) Accept SDK license
android.accept_sdk_license = True

# (str) python-for-android source dir (overridden by BUILDOZER_P4A_SOURCE_DIR in CI)
p4a.source_dir = /tmp/p4a

# (str) 本地 recipe 目录：仅覆盖 boost（增加 Python 3.11 兼容性补丁），libtorrent 仍用上游
p4a.local_recipes = ./recipes

[app:android.permissions]
INTERNET
WRITE_EXTERNAL_STORAGE
READ_EXTERNAL_STORAGE

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 0
