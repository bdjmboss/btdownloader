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
source.include_exts = py,png,jpg,kv,atlas,ttf

# (list) List of directory to exclude
source.exclude_dirs = tests, bin, recipes

# (version) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
requirements = kivy, android

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) List of supported Android permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (str) Android arch to build for
android.archs = armeabi-v7a,arm64-v8a

# (bool) Accept SDK license
android.accept_sdk_license = True

# (str) python-for-android branch to use
p4a.branch = stable

[app:android.permissions]
INTERNET
WRITE_EXTERNAL_STORAGE
READ_EXTERNAL_STORAGE

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 0
