#!/bin/bash
# 将应用推送到手机 Kivy Launcher 目录
# 使用方法: 在 WSL 或有 adb 的环境中执行: bash push_to_phone.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "检查 ADB 设备..."
if ! adb devices | grep -q "device$"; then
    echo "错误: 未检测到 ADB 设备"
    echo "请确保:"
    echo "  1. 手机通过 USB 连接电脑"
    echo "  2. 开启开发者选项 -> USB 调试"
    echo "  3. 在手机上授权 USB 调试"
    exit 1
fi

echo "创建 Kivy Launcher 目录..."
adb shell mkdir -p /sdcard/kivy/BtDownloader

echo "推送应用文件..."
# 将 main_launcher.py 推为 main.py
adb push main_launcher.py /sdcard/kivy/BtDownloader/main.py

# 推送其他依赖文件
if [ -f "buildozer.spec" ]; then
    adb push buildozer.spec /sdcard/kivy/BtDownloader/
fi

# 创建 android.txt 配置
ANDROID_TXT="/sdcard/kivy/BtDownloader/android.txt"
adb shell "echo 'title=BT下载器' > $ANDROID_TXT"
adb shell "echo 'author=BT Downloader Team' >> $ANDROID_TXT"
adb shell "echo 'orientation=portrait' >> $ANDROID_TXT"

echo ""
echo "========================================"
echo "推送完成！"
echo ""
echo "请在手机上:"
echo "  1. 打开 Kivy Launcher"
echo "  2. 在列表中找到 'BtDownloader'"
echo "  3. 点击运行即可"
echo "========================================"
