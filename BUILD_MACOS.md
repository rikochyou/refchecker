# macOS 打包教程（从零开始）

## 准备工作：安装 Xcode Command Line Tools

打开 **终端**（Terminal），输入：

```bash
xcode-select --install
```

弹窗点"安装"，完成后继续。

---

## 第一步：安装 Homebrew

Homebrew 是 macOS 的包管理器，用来装 Flutter 和其他工具。

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## 第二步：安装 Flutter

```bash
brew install --cask flutter
```

验证安装：

```bash
flutter doctor
```

看到绿色的勾就 OK。如果有红色警告，按提示修复即可。

## 第三步：拉取代码

```bash
git clone git@github.com:rikochyou/refchecker.git
cd refchecker
```

## 第四步：安装 Python 依赖 + 打包后端

```bash
pip3 install pyinstaller bibtexparser requests python-docx
pyinstaller --onefile --name refchecker_backend check_bib_crossref.py
cp dist/refchecker_backend backend/
```

## 第五步：打包 Flutter 应用

```bash
flutter pub get
flutter build macos
```

产物在 `build/macos/Build/Products/Release/refchecker_desktop.app`。

## 第六步：制作 dmg 分发包

```bash
# 创建文件夹
mkdir -p dist_macos/RefChecker.app/Contents/MacOS/backend
cp -r build/macos/Build/Products/Release/refchecker_desktop.app/* dist_macos/RefChecker.app/
cp backend/refchecker_backend dist_macos/RefChecker.app/Contents/MacOS/backend/

# 打包为 dmg
hdiutil create -volname RefChecker -srcfolder dist_macos -ov -format UDZO refchecker_macos.dmg
```

完成！`refchecker_macos.dmg` 就是可以分发的安装包。用户打开 dmg，把 RefChecker 拖进 Applications 即可使用。
