# BT下载器 - 手机版 APK 构建指南

## 方案一：使用 Buildozer 构建（推荐）

Buildozer 是 Kivy 官方推荐的打包工具，但需要在 Linux 环境下运行。

### 步骤 1：在 WSL 或 Linux 环境中准备

```bash
# 安装 buildozer 及其依赖
sudo apt-get update
sudo apt-get install -y python3-pip build-essential git python3-setuptools

# 安装 buildozer
pip3 install buildozer

# 安装 Android SDK/NDK 依赖（首次构建会自动下载）
sudo apt-get install -y openjdk-17-jre
```

### 步骤 2：构建 APK

```bash
# 进入项目目录
cd bt_phone

# 首次构建（会自动下载所有依赖）
buildozer android debug

# 或者构建发布版本
buildozer android release
```

### 步骤 3：获取 APK 文件

构建完成后，APK 文件位于：
```
bt_phone/bin/BT下载器-1.0.0-arm64-v8a-debug.apk
```

## 方案二：使用 Kivy Launcher 快速测试

如果不想构建完整 APK，可以使用 Kivy Launcher 来测试应用：

### 步骤 1：下载 Kivy Launcher

从 Google Play 或 F-Droid 下载 Kivy Launcher APK 并安装到手机。

### 步骤 2：部署应用

```bash
# 将项目文件复制到手机
adb push bt_phone /sdcard/kivy/btdownloader

# 或者使用 adb 安装 Kivy Launcher
adb install KivyLauncher.apk
```

### 步骤 3：运行应用

1. 打开手机上的 Kivy Launcher
2. 选择 "btdownloader" 项目
3. 点击运行

## 方案三：在 Windows 上使用 Buildozer（WSL）

如果使用 Windows 10/11，可以使用 WSL (Windows Subsystem for Linux)：

```bash
# 安装 WSL
wsl --install

# 在 WSL 中执行上述 Linux 步骤
```

## 注意事项

1. **首次构建时间较长**：Buildozer 首次构建需要下载 Android SDK、NDK 等依赖，可能需要 30 分钟以上。

2. **libtorrent 交叉编译**：libtorrent 需要为 Android 交叉编译，Buildozer 会自动处理。

3. **存储权限**：Android 13+ 需要特殊处理存储权限，应用已在 manifest 中声明了相关权限。

4. **测试设备**：建议使用真实设备进行测试，模拟器可能不支持 BT 功能。

5. **文件传输**：可以通过 adb push 或直接下载 APK 到手机安装。

## 常见问题

### Q: 构建时提示缺少 Java？
A: 安装 OpenJDK: `sudo apt-get install openjdk-17-jre`

### Q: 如何在真机上调试？
A: 使用 `adb logcat` 查看日志，或在代码中添加 `print()` 输出。

### Q: APK 体积较大怎么办？
A: Release 版本会自动压缩，可在 buildozer.spec 中配置压缩选项。
