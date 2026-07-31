#!/bin/bash
# BT下载器 APK 构建环境设置脚本
# 在 WSL Ubuntu 中执行此脚本

set -e

echo "=== BT下载器 APK 构建环境设置 ==="

# 更新系统
sudo apt-get update
sudo apt-get upgrade -y

# 安装构建依赖
echo "安装构建依赖..."
sudo apt-get install -y \
    ant \
    autoconf \
    automake \
    autopoint \
    cmake \
    g++ \
    gcc \
    git \
    libffi-dev \
    libltdl-dev \
    libtool \
    libssl-dev \
    make \
    openjdk-17-jdk \
    patch \
    pkg-config \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    unzip \
    wget \
    zip \
    zlib1g-dev

# 设置 Java 环境
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

echo "Java 版本:"
java -version

# 创建 Python 虚拟环境
cd ~
python3 -m venv buildozer-env
source buildozer-env/bin/activate

# 安装 buildozer 和 python-for-android
echo "安装 buildozer..."
pip install --upgrade pip
pip install buildozer cython

# 设置 Android SDK 路径
export ANDROIDSDK="/mnt/c/Users/King/AppData/Local/Android/Sdk"
export ANDROIDNDK="/mnt/c/Users/King/AppData/Local/Android/Sdk/ndk"
export ANDROIDAPI=33
export NDKAPI=24

echo "Android SDK: $ANDROIDSDK"
echo "Android NDK: $ANDROIDNDK"

# 如果 NDK 不存在，下载安装
if [ ! -d "$ANDROIDNDK" ]; then
    echo "下载 Android NDK..."
    wget -q https://dl.google.com/android/repository/android-ndk-r27c-linux-x86_64.zip -O /tmp/ndk.zip
    unzip -q /tmp/ndk.zip -d "$(dirname $ANDROIDNDK)"
    rm /tmp/ndk.zip
    export ANDROIDNDK="$(dirname $ANDROIDNDK)/android-ndk-r27c"
fi

# 写入环境变量到 profile
cat >> ~/.bashrc << 'EOF'
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH
export ANDROIDSDK="/mnt/c/Users/King/AppData/Local/Android/Sdk"
export ANDROIDNDK="/mnt/c/Users/King/AppData/Local/Android/Sdk/ndk"
export ANDROIDAPI=33
export NDKAPI=24
EOF

echo ""
echo "=== 环境设置完成 ==="
echo "请运行以下命令构建 APK:"
echo ""
echo "  source ~/buildozer-env/bin/activate"
echo "  cd /mnt/c/tools/Hermes-windows/workspace/Bt下载软件/bt_phone"
echo "  buildozer android debug"
echo ""
