#!/usr/bin/env bash
# =============================================================================
#  iyf/tv/patch.sh —— tv.ifvod.classic（Android TV 客户端）的抗版本变化 VIP/去广告补丁。
#
#  用法：   bash patch.sh <input.apk> [output.apk]
#  示例：   bash patch.sh ~/1-1779820631.apk ~/atv_patched.apk
#
#  目录结构：patch.sh      —— 本流水线（装依赖、反编译、组装、签名）
#            engine.py     —— 把补丁应用到反编译出的 smali
#            repackage.py  —— 把新 dex 换回原始 apk
#            patches/      —— 每个功能点一个 *.patch，按文件名顺序应用
#
#  流水线：
#    1. 用 apktool 把 APK 反编译成 smali
#    2. engine.py 应用每个 patches/*.patch（语义化、按地标锚定的锚点）
#    3. 只重新组装 dex（不跑 aapt / 资源重建 —— 从而绕开 aapt1 和 aapt2 都会在本应用
#       $ 命名资源上失败的问题），然后 repackage.py 把它换回原始 apk（resources/.so
#       保持逐字节不变），
#    4. zipalign 并签名（v1+v2+v3），用 ~/.vip_patch 里可复用的密钥。
#
#  要新增/调整某项行为，改 patches/ 里的文件即可，不用动这个脚本。
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES="$HERE/patches"

IN="${1:-}"; OUT="${2:-}"
[ -n "$IN" ] || { echo "用法: $0 <input.apk> [output.apk]"; exit 2; }
[ -f "$IN" ] || { echo "!! 找不到文件: $IN"; exit 2; }
IN="$(readlink -f "$IN")"
OUT="${OUT:-${IN%.apk}_vip.apk}"

TOOLHOME="$HOME/.vip_patch"; KS="$TOOLHOME/hw.keystore"; mkdir -p "$TOOLHOME"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/vippatch.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT
DEC="$WORK/dec"

echo "== [1/6] 工具链 =="
need=0; for t in apktool apksigner zipalign keytool java python3; do command -v "$t" >/dev/null 2>&1 || need=1; done
if [ "$need" = 1 ]; then
  echo "   通过 apt 安装工具链（sudo）..."
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
       default-jdk-headless apktool apksigner zipalign python3
fi
echo "   apktool $(apktool --version 2>/dev/null) | apksigner $(apksigner --version 2>/dev/null)"

echo "== [2/6] 反编译 =="
apktool d -f -o "$DEC" "$IN" >/dev/null
echo "   已反编译 -> $DEC"

echo "== [3/6] 应用补丁 ($PATCHES) =="
python3 "$HERE/engine.py" "$DEC" "$PATCHES"

echo "== [4/6] 组装 dex（资源原样保留；此处无法做 apktool 完整重建，"
echo "         因为 aapt1 和 aapt2 都会拒绝本应用的 \$ 命名资源） =="
set +e
apktool b -o "$WORK/rebuilt.apk" "$DEC" > "$WORK/apktool_build.log" 2>&1
set -e
if ! ls "$DEC"/build/apk/classes*.dex >/dev/null 2>&1; then
  echo "!! dex 组装失败。构建日志末尾："; tail -n 40 "$WORK/apktool_build.log"; exit 1
fi
echo "   dex 已组装"

echo "== [5/6] 重新打包（把 dex 换回原始 apk） =="
python3 "$HERE/repackage.py" "$IN" "$DEC/build/apk" "$WORK/unsigned.apk"

echo "== [6/6] align + 签名 =="
zipalign -f -p 4 "$WORK/unsigned.apk" "$WORK/aligned.apk"
zipalign -c -p 4 "$WORK/aligned.apk" >/dev/null && echo "   对齐: OK"
if [ ! -f "$KS" ]; then
  echo "   生成可复用的签名密钥 -> $KS"
  keytool -genkeypair -v -keystore "$KS" -alias vip -keyalg RSA -keysize 2048 \
      -validity 10000 -storepass android -keypass android -dname "CN=VIP Patch" >/dev/null 2>&1
fi
rm -f "$OUT"
apksigner sign --ks "$KS" --ks-pass pass:android --key-pass pass:android --out "$OUT" "$WORK/aligned.apk"
echo
apksigner verify --print-certs "$OUT" | sed -n '1,6p'
echo
echo ">>> 完成: $OUT"
echo ">>> 安装:  adb uninstall tv.ifvod.classic ; adb install -r \"$OUT\""
