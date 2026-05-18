#!/bin/bash
# 将安装程序打包为 .dmg（仅 macOS）
set -e

APP_DIR="dist/一键发布工具安装程序"
DMG_NAME="一键发布工具安装程序"
DMG_FILE="dist/${DMG_NAME}.dmg"
TMP_DIR="dist/_dmg_temp"

if [ ! -d "$APP_DIR" ]; then
    echo "错误: 未找到 $APP_DIR，请先运行 build_all.sh"
    exit 1
fi

echo "正在生成 .dmg..."

rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
cp -R "$APP_DIR/" "$TMP_DIR/"

# macOS 安装惯例：Applications 快捷方式
ln -sf /Applications "$TMP_DIR/Applications"

hdiutil create -volname "$DMG_NAME" \
    -srcfolder "$TMP_DIR" \
    -ov -format UDZO \
    "$DMG_FILE"

rm -rf "$TMP_DIR"

echo ""
echo "✓ 已生成: $DMG_FILE"
echo "  用户双击 .dmg 把应用拖到 Applications 文件夹即可安装"
