#!/usr/bin/env bash
# =============================================================================
#  iyf/windows/patch.sh —— 从官方 NSIS 安装包构建一个免安装、去广告、全 VIP 的
#  爱壹帆（iyf）Windows 版应用（Electron）。打过补丁的 app.asar 无需对 exe 重新签名即可加载。
#
#  用法：  bash patch.sh [iyf_Setup_x.y.z.exe] [output.zip]
#  默认输入：~/iyf_Setup_3.1.5.exe
#  默认输出：~/iyf_3.1.5_portable_vip.zip
#
#  目录结构：patch.sh   —— 本流水线（装依赖、解包、重新打包、打 zip）
#            engine.py  —— 应用补丁（在下方被调用）
#            patches/   —— 每个功能点一个 *.patch，按文件名顺序应用
#  要新增/调整某项行为，改 patches/ 里的文件即可，不用动这个脚本。
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES="$HERE/patches"

IN="${1:-$HOME/iyf_Setup_3.1.5.exe}"
[ -f "$IN" ] || { echo "!! 找不到安装包: $IN"; exit 2; }
IN="$(readlink -f "$IN")"
OUT="${2:-$HOME/iyf_3.1.5_portable_vip.zip}"
NAME="$(basename "${OUT%.zip}")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/iyfpatch.XXXXXX")"; trap 'rm -rf "$WORK"' EXIT

echo "== [1/7] 工具链 =="
command -v 7z    >/dev/null 2>&1 || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq p7zip-full
export PATH="$(npm root -g)/../bin:$PATH"
command -v asar  >/dev/null 2>&1 || npm i -g @electron/asar >/dev/null 2>&1
ASAR="$(command -v asar || echo 'npx --yes @electron/asar')"
echo "   7z=$(command -v 7z)  asar=$ASAR  node=$(node -v)  python3=$(command -v python3)"

echo "== [2/7] 解开 NSIS 安装包 =="
7z x -y -o"$WORK/nsis" "$IN" >/dev/null
APP7Z="$(find "$WORK/nsis" -name 'app-64.7z' | head -1)"
[ -n "$APP7Z" ] || { echo "!! 找不到 app-64.7z（可能不是 electron-builder 的 NSIS 安装包？）"; exit 1; }

echo "== [3/7] 解开 Electron 应用负载 =="
7z x -y -o"$WORK/app" "$APP7Z" >/dev/null
ASARF="$WORK/app/resources/app.asar"
[ -f "$ASARF" ] || { echo "!! 找不到 resources/app.asar"; exit 1; }

echo "== [4/7] 解包 app.asar =="
$ASAR extract "$ASARF" "$WORK/asar_src"

echo "== [5/7] 应用补丁 ($PATCHES) =="
python3 "$HERE/engine.py" "$WORK/asar_src" "$PATCHES"

echo "== [6/7] 重新打包 app.asar =="
rm -f "$ASARF"
$ASAR pack "$WORK/asar_src" "$ASARF"

echo "== [7/7] 打包成 zip =="
mv "$WORK/app" "$WORK/$NAME"
rm -f "$OUT"
( cd "$WORK" && 7z a -tzip -mcu=on -mx=3 "$OUT" "$NAME" >/dev/null )
echo
echo ">>> 完成: $OUT  ($(du -h "$OUT" | cut -f1))"
echo ">>> 在 Windows 上：解压后运行  $NAME/爱壹帆.exe  （无需安装）"
echo ">>>   加上  --inspect  可启用右键 Inspect / DevTools"
