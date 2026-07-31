import os
import sh
from pythonforandroid.toolchain import Recipe, current_directory, shprint
from pythonforandroid.logger import info, warning
from pythonforandroid.util import ensure_dir


class LibtorrentRecipe(Recipe):
    version = '2.0.13'
    url = 'https://github.com/arvidn/libtorrent/releases/download/v{version}/libtorrent-{version}.tar.gz'
    depends = ['python3', 'openssl', 'boost']
    patches = []

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        info('Building libtorrent for Android ARM64...')

    def build_arch(self, arch):
        super().build_arch(arch)

        build_dir = self.get_build_dir(arch.arch)
        with current_directory(build_dir):
            # Set up Android NDK toolchain
            ndk = self.ctx.ndk
            ndk_api = self.ctx.ndk_api

            # Determine toolchain paths
            if arch.arch == 'arm64-v8a':
                clang = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android{ndk_api}-clang'
                clangxx = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android{ndk_api}-clang++'
                ar = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar'
                ranlib = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ranlib'
                strip = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip'
            elif arch.arch == 'armeabi-v7a':
                clang = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi{ndk_api}-clang'
                clangxx = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi{ndk_api}-clang++'
                ar = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar'
                ranlib = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ranlib'
                strip = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip'
            else:
                raise ValueError(f'Unsupported arch: {arch.arch}')

            # Get Python include paths
            python_include = self.ctx.python_include_dir
            python_version = self.ctx.python_version

            # Build libtorrent with cmake
            cmake_build_dir = os.path.join(build_dir, 'build')
            ensure_dir(cmake_build_dir)

            with current_directory(cmake_build_dir):
                info('Running cmake for libtorrent...')

                cmake_env = os.environ.copy()
                cmake_env.update({
                    'CC': clang,
                    'CXX': clangxx,
                    'AR': ar,
                    'RANLIB': ranlib,
                    'STRIP': strip,
                    'ANDROID_NDK': ndk,
                    'ANDROID_ABI': arch.arch,
                })

                # Get boost and openssl paths from the build context
                boost_build = os.path.join(self.ctx.build_dir, 'other_builds', 'boost', arch.arch)
                openssl_build = os.path.join(self.ctx.build_dir, 'other_builds', 'openssl', arch.arch)

                cmake_args = [
                    '..',
                    '-DCMAKE_SYSTEM_NAME=Android',
                    f'-DCMAKE_SYSTEM_VERSION={ndk_api}',
                    f'-DCMAKE_ANDROID_ARCH_ABI={arch.arch}',
                    '-DCMAKE_ANDROID_NDK=' + ndk,
                    '-DCMAKE_C_COMPILER=' + clang,
                    '-DCMAKE_CXX_COMPILER=' + clangxx,
                    '-DCMAKE_BUILD_TYPE=Release',
                    '-DENABLE_CXX_EXCEPTIONS=ON',
                    '-DENABLE_CFFI=ON',
                    '-DBUILD_SHARED_LIBS=ON',
                    '-DBUILD_STATIC_LIBS=OFF',
                    '-DUSE_SSL=ON',
                    f'-DOPENSSL_ROOT_DIR={openssl_build}',
                    f'-DBOOST_ROOT={boost_build}',
                    '-DBOOST_LIBRARYDIR=' + os.path.join(boost_build, 'lib'),
                    '-Dpython3_VERSION=' + python_version,
                    '-Dpython3_INCLUDE_DIR=' + python_include,
                ]

                try:
                    shprint(sh.cmake, *cmake_args, _env=cmake_env)
                except Exception as e:
                    warning(f'cmake failed: {e}')
                    raise

                info('Building libtorrent...')
                try:
                    shprint(sh.make, '-j4', _env=cmake_env)
                except Exception as e:
                    warning(f'make failed: {e}')
                    raise

            # Build Python bindings
            info('Building Python bindings for libtorrent...')
            bindings_dir = os.path.join(build_dir, 'bindings', 'python')
            if os.path.exists(bindings_dir):
                with current_directory(bindings_dir):
                    # Copy the built library to the bindings directory
                    lib_path = os.path.join(cmake_build_dir, 'libtorrent-rasterbar.so')
                    if os.path.exists(lib_path):
                        shprint(sh.cp, lib_path, '.')

                    python_env = os.environ.copy()
                    python_env.update({
                        'CC': clang,
                        'CXX': clangxx,
                        'AR': ar,
                        'BOOST_ROOT': boost_build,
                        'OPENSSL_ROOT': openssl_build,
                        'TORRENT_LIB': cmake_build_dir,
                    })

                    # Build the Python bindings
                    shprint(sh.python, 'setup.py', 'build_ext',
                            f'--b2-args=python={python_version} linkflags=-L{cmake_build_dir}',
                            _env=python_env)

                    # Install the built module
                    libtorrent_so = os.path.join(bindings_dir, 'libtorrent')
                    if os.path.exists(libtorrent_so):
                        self.install_libs(arch, libtorrent_so)

    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)
        info('libtorrent build complete for {}'.format(arch.arch))


recipe = LibtorrentRecipe()
