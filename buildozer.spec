[app]

# (str) Title of your application
title = BT下载器

# (str) Package name
package.name = btdownloader

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (version) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy

# (list) Garden requirements
garden_requirements =

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (list) List of supported Android permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

# (str) Android API to use
android.api = 33

# (str) Android minimum API level
android.minapi = 24

# (str) Android SDK version to use
android.sdk = 24.0.1

# (str) Android NDK version to use
android.ndk = 25b

# (str) Android NDK directory (if empty, it will be automatically downloaded.)
#android.ndk_path =

# (str) Android SDK directory (if empty, it will be automatically downloaded.)
#android.sdk_path =

# (str) android multiarch (if empty, it will be automatically detected.)
#android.multiarch =

# (str) Android archive version to use
android.archs = arm64-v8a, armeabi-v7a

# (str) Android entry point, default is ok for Kivy-based app
android.entrypoint = org.kivy.android.PythonActivity

# (list) List of Java .jar files to add to the libs so that pyjnius can access
# their classes. Don't add jars that you do not need, since extra jars can slow
# down the build process.
#android.add_jars = foo.jar,bar.jar

# (list) List of Java files to add to the android project (very useful to
# override the default manifest)
#android.add_src =

# (list) Android AAR archives to add (currently works only with sdl2-bootstrap)
#android.add_aars =

# (list) Gradle dependencies to add (currently works only with sdl2-bootstrap)
#android.gradle_dependencies =

# (list) Android permissions to add
# see https://python-for-android.readthedocs.io/en/latest/permissions/
#android.extra_permissions =

# (str) the package name for the application
#android.package = org.example.btdownloader

# (str) the class name for the Activity
#android.activity_class_name = org.kivy.android.PythonActivity

# (str) the class name for the test Activity
#android.test_activity_class_name = org.kivy.android.PythonActivity

# (str) the main Activity to launch
#android.launch_activity = org.kivy.android.PythonActivity

# (str) If True, then try to copy libs from the existing project instead of
# compiling them. Used only for android platform.
android.use_aar = False

#
# AndroidX support
#
# Set to True if your application needs AndroidX support.
#android.enable_androidx = False

#
# The format for the following permission
# android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE
#

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0

# (str) Path to build artifact storage, relative to the working directory
#build_dir = ./.buildozer

# (str) Path to use for cache, e.g. buildozer dependencies
#cache_dir = .buildozer/cache
