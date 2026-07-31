#!/bin/bash
# BT下载器 APK 自动构建脚本
# 使用方法: 在 WSL Ubuntu 中执行: bash build_apk.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================"
echo "BT下载器 APK 自动构建"
echo "========================================"

# 检测并设置环境变量
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export ANDROIDSDK="${ANDROIDSDK:-/mnt/c/Users/King/AppData/Local/Android/Sdk}"
export ANDROIDNDK="${ANDROIDNDK:-$ANDROIDSDK/ndk}"
export ANDROIDAPI="${ANDROIDAPI:-33}"
export NDKAPI="${NDKAPI:-24}"
export PATH="$JAVA_HOME/bin:$PATH"

echo "Java: $JAVA_HOME"
echo "SDK: $ANDROIDSDK"
echo "NDK: $ANDROIDNDK"
echo ""

# 检查 Java
if ! command -v java &> /dev/null; then
    echo "错误: 未找到 Java，请先安装 openjdk-17-jdk"
    exit 1
fi

java -version 2>&1 | head -1

# 检查 Android SDK
if [ ! -d "$ANDROIDSDK" ]; then
    echo "错误: 未找到 Android SDK ($ANDROIDSDK)"
    exit 1
fi

# 检查/安装 NDK
NDK_VERSION="android-ndk-r27c"
if [ ! -d "$ANDROIDNDK/$NDK_VERSION" ]; then
    echo "下载 Android NDK..."
    mkdir -p "$ANDROIDNDK"
    NDK_URL="https://dl.google.com/android/repository/${NDK_VERSION}-linux-x86_64.zip"
    wget -q --show-progress "$NDK_URL" -O /tmp/ndk.zip
    unzip -q /tmp/ndk.zip -d "$ANDROIDNDK"
    rm /tmp/ndk.zip
fi
export ANDROIDNDK="$ANDROIDNDK/$NDK_VERSION"
echo "NDK: $ANDROIDNDK"

# 激活 Python 环境
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
else
    # 创建虚拟环境
    python3 -m venv "$PROJECT_DIR/venv"
    source "$PROJECT_DIR/venv/bin/activate"
    pip install --upgrade pip
    pip install buildozer cython
fi

# 安装 buildozer
if ! command -v buildozer &> /dev/null; then
    echo "安装 buildozer..."
    pip install buildozer cython
fi

# 设置 buildozer 环境变量
export ANDROIDSDK
export ANDROIDNDK
export ANDROIDAPI
export NDKAPI

echo ""
echo "开始构建 APK..."
echo "这可能需要 30-60 分钟，首次构建需要下载很多依赖..."
echo ""

# 执行构建
buildozer android debug

echo ""
echo "========================================"
echo "构建完成！"
echo "APK 文件位于: $PROJECT_DIR/bin/"
echo "========================================"

# 显示生成的 APK
find bin -name "*.apk" -type f 2>/dev/null | while read apk; do
    echo "  - $apk ($(du -h "$apk" | cut -f1))"
done
