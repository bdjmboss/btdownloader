import os
import sh
from pythonforandroid.toolchain import Recipe, current_directory, shprint
from pythonforandroid.logger import info, warning
from pythonforandroid.util import ensure_dir


class LibtorrentRecipe(Recipe):
    version = 'RC_2_1'
    url = 'https://github.com/arvidn/libtorrent/releases/download/{version}/libtorrent-{version}.tar.gz'
    depends = ['python3', 'openssl', 'boost']
    patches = []

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        info(f'Building libtorrent {self.version} for Android {arch.arch}...')

    def build_arch(self, arch):
        super().build_arch(arch)

        ndk = self.ctx.ndk
        ndk_api = self.ctx.ndk_api
        build_dir = self.get_build_dir(arch.arch)

        # Toolchain paths
        if arch.arch == 'arm64-v8a':
            clang = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android{ndk_api}-clang'
            clangxx = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android{ndk_api}-clang++'
        elif arch.arch == 'armeabi-v7a':
            clang = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi{ndk_api}-clang'
            clangxx = f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi{ndk_api}-clang++'
        else:
            raise ValueError(f'Unsupported arch: {arch.arch}')

        boost_build = os.path.join(self.ctx.build_dir, 'other_builds', 'boost', arch.arch)
        openssl_build = os.path.join(self.ctx.build_dir, 'other_builds', 'openssl', arch.arch)
        python_include = self.ctx.python_include_dir
        python_version = self.ctx.python_version

        # Step 1: Build libtorrent C++ library with cmake
        cmake_build_dir = os.path.join(build_dir, 'build')
        ensure_dir(cmake_build_dir)

        with current_directory(cmake_build_dir):
            info('Configuring libtorrent C++ library...')

            cmake_env = os.environ.copy()
            cmake_env.update({
                'CC': clang,
                'CXX': clangxx,
                'AR': f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar',
                'RANLIB': f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ranlib',
                'STRIP': f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip',
            })

            cmake_args = [
                '..',
                '-DCMAKE_SYSTEM_NAME=Android',
                f'-DCMAKE_SYSTEM_VERSION={ndk_api}',
                f'-DCMAKE_ANDROID_ARCH_ABI={arch.arch}',
                f'-DCMAKE_ANDROID_NDK={ndk}',
                f'-DCMAKE_C_COMPILER={clang}',
                f'-DCMAKE_CXX_COMPILER={clangxx}',
                '-DCMAKE_BUILD_TYPE=Release',
                '-DBUILD_SHARED_LIBS=ON',
                '-DBUILD_STATIC_LIBS=OFF',
                '-DUSE_SSL=ON',
                '-DENABLE_CXX_EXCEPTIONS=ON',
                '-DENABLE_CFFI=ON',
                f'-DOPENSSL_ROOT_DIR={openssl_build}',
                f'-DBOOST_ROOT={boost_build}',
                f'-DBOOST_LIBRARYDIR={os.path.join(boost_build, "lib")}',
                '-Dpython3_VERSION=' + python_version,
                '-Dpython3_INCLUDE_DIR=' + python_include,
                '-DANTLR_EXECUTABLE=',
                '-DWEBTORRENT=OFF',
                '-DUSE_ED25519=ON',
            ]

            try:
                shprint(sh.cmake, *cmake_args, _env=cmake_env)
            except Exception as e:
                warning(f'cmake failed: {e}')
                raise

            info('Compiling libtorrent C++ library...')
            try:
                shprint(sh.make, '-j4', _env=cmake_env)
            except Exception as e:
                warning(f'make failed: {e}')
                raise

        # Step 2: Build Python bindings
        info('Building Python bindings...')
        bindings_dir = os.path.join(build_dir, 'bindings', 'python')

        with current_directory(bindings_dir):
            python_env = os.environ.copy()
            python_env.update({
                'CC': clang,
                'CXX': clangxx,
                'AR': f'{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar',
                'BOOST_ROOT': boost_build,
                'OPENSSL_ROOT': openssl_build,
                'TORRENT_LIB': cmake_build_dir,
                'PYTHON_INCLUDE_DIR': python_include,
                'PYTHON_VERSION': python_version,
            })

            try:
                shprint(sh.python, 'setup.py', 'build_ext',
                        '--config-mode=distutils',
                        f'--b2-args=python={python_version}'
                        f' libtorrent-link=static'
                        f' boost-link=static'
                        f' crypto=openssl'
                        f' cxxstd=17'
                        f' libtorrent-python-pic=on',
                        _env=python_env)
            except Exception as e:
                warning(f'Python bindings build failed: {e}')
                raise

            # Install the built module
            libtorrent_so = self.find_library('libtorrent', bindings_dir)
            if libtorrent_so:
                info(f'Installing libtorrent Python module from {libtorrent_so}...')
                self.install_libs(arch, libtorrent_so)
            else:
                raise Exception('Could not find built libtorrent Python module')

    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)
        info(f'libtorrent {self.version} build complete for {arch.arch}')


recipe = LibtorrentRecipe()
