# -*- coding: utf-8 -*-
"""libtorrent Python 绑定 - Android 交叉编译 recipe

参考 libtorrent 官方 Android CI（boost 1.75.0 + b2 + NDK clang）。
自包含：自动下载 boost 并 bootstrap b2，然后用 b2 构建 libtorrent Python 绑定。
"""

import os
import sh
from pythonforandroid.toolchain import Recipe, current_directory, shprint
from pythonforandroid.logger import info, warning
from pythonforandroid.util import ensure_dir


class LibtorrentRecipe(Recipe):
    version = '2.0.12'
    url = 'https://github.com/arvidn/libtorrent/archive/refs/tags/v{version}.tar.gz'
    depends = ['python3', 'openssl']
    patches = []
    need_stl_shared = True

    # 使用的 boost 版本（libtorrent 要求 >= 1.70，官方 CI 用 1.75.0）
    boost_version = '1.75.0'

    def _ndk_path(self):
        """获取 NDK 路径（兼容 self.ctx.ndk 为对象或字符串）"""
        ndk = self.ctx.ndk
        if hasattr(ndk, 'ndk_dir'):
            return ndk.ndk_dir
        return str(ndk)

    def _prepare_boost(self, arch):
        """下载 boost 源码并 bootstrap b2"""
        boost_ver_us = self.boost_version.replace('.', '_')
        boost_build_dir = os.path.join(
            self.ctx.build_dir, 'other_builds', 'boost-src', arch.arch)
        ensure_dir(boost_build_dir)

        boost_src = f'boost_{boost_ver_us}'
        boost_dir = os.path.join(boost_build_dir, boost_src)
        tarball = f'{boost_src}.tar.bz2'
        url = (f'https://downloads.sourceforge.net/project/boost/'
               f'boost/{self.boost_version}/{tarball}')

        with current_directory(boost_build_dir):
            if not os.path.exists(tarball):
                info(f'下载 boost {self.boost_version}...')
                shprint(sh.wget, '-q', '-O', tarball, url, _timeout=600)
            if not os.path.exists(boost_src):
                info('解压 boost...')
                shprint(sh.tar, 'xf', tarball)

        with current_directory(boost_dir):
            if not os.path.exists('b2'):
                info('Bootstrap boost build engine...')
                bash = sh.Command('bash')
                shprint(bash, 'bootstrap.sh')
            if not os.path.exists('boost/version.hpp'):
                info('生成 boost headers...')
                shprint(sh.Command('./b2'), 'headers', '-j2')

        info(f'boost 准备完成: {boost_dir}')
        return boost_dir

    def _get_openssl_paths(self, arch):
        """从 openssl recipe 获取头文件和库路径"""
        try:
            openssl_recipe = Recipe.get_recipe('openssl', self.ctx)
            oenv = openssl_recipe.get_recipe_env(arch)
            inc = oenv.get('OPENSSL_INCLUDE', '')
            lib = oenv.get('OPENSSL_LIB', '')
            if inc and lib:
                return inc, lib
        except Exception as e:
            warning(f'获取 openssl recipe env 失败: {e}')

        # 回退：在 p4a 构建目录中查找
        base = os.path.join(self.ctx.build_dir, 'other_builds',
                            'openssl', arch.arch)
        inc = os.path.join(base, 'include')
        lib = os.path.join(base, 'lib')
        if not os.path.exists(inc):
            # 尝试其他常见布局
            for sub in ['openssl', 'openssl1.1']:
                alt = os.path.join(self.ctx.build_dir, 'other_builds',
                                   sub, arch.arch)
                if os.path.exists(os.path.join(alt, 'include')):
                    return os.path.join(alt, 'include'), os.path.join(alt, 'lib')
        return inc, lib

    def build_arch(self, arch):
        super().build_arch(arch)
        info(f'构建 libtorrent {self.version} for Android {arch.arch}...')

        env = self.get_recipe_env(arch)

        # ---- 1. 准备 boost ----
        boost_dir = self._prepare_boost(arch)
        env['BOOST_ROOT'] = boost_dir
        env['BOOST_BUILD_PATH'] = boost_dir

        # ---- 2. Python 路径 ----
        py_recipe = self.ctx.python_recipe
        py_include = py_recipe.include_root(arch.arch)
        py_link_root = py_recipe.link_root(arch.arch)
        py_ver_full = py_recipe.version  # e.g. "3.11.15"
        py_parts = py_ver_full.split('.')
        py_major_minor = '.'.join(py_parts[:2])  # "3.11"
        info(f'Python {py_major_minor}: include={py_include} link={py_link_root}')

        # ---- 3. OpenSSL 路径 ----
        ssl_inc, ssl_lib = self._get_openssl_paths(arch)
        info(f'OpenSSL: include={ssl_inc} lib={ssl_lib}')

        # ---- 4. NDK 编译器路径 ----
        ndk = self._ndk_path()
        ndk_api = self.ctx.ndk_api
        llvm_prebuilt = os.path.join(ndk, 'toolchains/llvm/prebuilt/linux-x86_64')
        sysroot = os.path.join(llvm_prebuilt, 'sysroot')

        if arch.arch == 'arm64-v8a':
            cxx = os.path.join(llvm_prebuilt, f'aarch64-linux-android{ndk_api}-clang++')
            arch_tag = 'arm64'
        elif arch.arch == 'armeabi-v7a':
            cxx = os.path.join(llvm_prebuilt, f'armv7a-linux-androideabi{ndk_api}-clang++')
            arch_tag = 'arm'
        elif arch.arch == 'x86_64':
            cxx = os.path.join(llvm_prebuilt, f'x86_64-linux-android{ndk_api}-clang++')
            arch_tag = 'x86_64'
        else:
            raise ValueError(f'不支持的架构: {arch.arch}')

        info(f'NDK CXX: {cxx}')
        info(f'Sysroot: {sysroot}')

        # ---- 5. 生成 user-config.jam ----
        user_config = os.path.join(os.path.expanduser('~'), 'user-config.jam')
        with open(user_config, 'w') as f:
            f.write(f'''# 自动生成 - libtorrent Android 交叉编译配置
import os ;

using python
    : {py_major_minor}
    :
    : {py_include}
    : {py_link_root}
    ;

using clang-linux : {arch_tag}
    : {cxx}
    : <cxxflags>-fPIC
      <cxxflags>-fvisibility=hidden
      <cxxflags>-fvisibility-inlines-hidden
      <cxxflags>-std=c++17
      <cxxflags>--sysroot={sysroot}
      <linkflags>--sysroot={sysroot}
      <linkflags>-fPIC
    ;
''')
        info(f'已生成 user-config.jam: {user_config}')

        # ---- 6. 生成 boost-build.jam ----
        build_dir = self.get_build_dir(arch.arch)
        with current_directory(build_dir):
            with open('boost-build.jam', 'w') as f:
                f.write(f'boost-build {boost_dir}/tools/build/src ;\n')

        # ---- 7. 用 b2 构建 libtorrent Python 绑定 ----
        bindings_dir = os.path.join(build_dir, 'bindings', 'python')
        b2 = sh.Command(os.path.join(boost_dir, 'b2'))

        b2_args = [
            'libtorrent-link=static',
            'boost-link=static',
            'crypto=openssl',
            f'openssl-include={ssl_inc}',
            f'openssl-lib={ssl_lib}',
            f'toolset=clang-linux-{arch_tag}',
            'target-os=android',
            'release',
            'cxxstd=17',
            f'python={py_major_minor}',
            '-j2',
            '--hash',
        ]

        info(f'b2 构建参数: {" ".join(b2_args)}')
        with current_directory(bindings_dir):
            shprint(b2, *b2_args, _env=env, _timeout=1800)

        # ---- 8. 查找并安装 .so ----
        so_file = self._find_so(bindings_dir)
        if so_file:
            info(f'安装 libtorrent Python 模块: {so_file}')
            self.install_libs(arch, so_file)
        else:
            # 在整个构建目录中搜索
            so_file = self._find_so(build_dir)
            if so_file:
                info(f'安装 libtorrent Python 模块(宽搜索): {so_file}')
                self.install_libs(arch, so_file)
            else:
                raise Exception('未找到编译产物 libtorrent*.so')

    def _find_so(self, search_dir):
        """查找编译生成的 libtorrent .so 文件"""
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.startswith('libtorrent') and f.endswith('.so'):
                    return os.path.join(root, f)
        return None

    def postbuild_arch(self, arch):
        super().postbuild_arch(arch)
        info(f'libtorrent {self.version} 构建完成 ({arch.arch})')


recipe = LibtorrentRecipe()
