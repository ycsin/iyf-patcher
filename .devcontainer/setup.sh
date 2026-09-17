#!/usr/bin/env bash
# Installs the toolchain both pipelines need:
#   tv/      -> apktool apksigner zipalign keytool java python3
#   windows/ -> 7z node npm asar (@electron/asar)
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
# Pinned to the latest 2.x on purpose: tv/patch.py & tv/patch.sh read the assembled dex
# from <decoded>/build/apk/classes*.dex, which is apktool 2.x layout. Override if you
# want to try 3.x:  APKTOOL_VERSION=3.0.3 bash .devcontainer/setup.sh
APKTOOL_VERSION="${APKTOOL_VERSION:-2.12.1}"

echo "== apt packages =="
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends \
     default-jdk-headless \
     apksigner \
     zipalign \
     python3 \
     p7zip-full \
     unzip curl ca-certificates
#    default-jdk-headless brings BOTH `java` and `keytool`.
#    Ubuntu also ships an `apktool` package, but it lags upstream badly — we take the
#    real jar below instead, since old apktool chokes on recent APKs.
#    p7zip-full is transitional on 24.04: it pulls in `7zip`, which provides /usr/bin/7z.

echo "== apktool ${APKTOOL_VERSION} (upstream jar + wrapper) =="
VER="$APKTOOL_VERSION"
sudo mkdir -p /opt/apktool
sudo curl -fsSL -o /opt/apktool/apktool.jar \
     "https://github.com/iBotPeaches/Apktool/releases/download/v${VER}/apktool_${VER}.jar"
sudo curl -fsSL -o /opt/apktool/apktool \
     "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool"
sudo chmod +x /opt/apktool/apktool
# wrapper looks for /usr/local/bin/apktool.jar next to itself; symlink both into PATH
sudo ln -sf /opt/apktool/apktool.jar /usr/local/bin/apktool.jar
sudo ln -sf /opt/apktool/apktool     /usr/local/bin/apktool

echo "== @electron/asar (Windows/Electron pipeline) =="
# node comes from the devcontainer node feature; its global prefix is user-writable, no sudo
npm i -g @electron/asar >/dev/null 2>&1 || echo "  (npm global install failed — patch.py/patch.sh fall back to 'npx --yes @electron/asar')"

echo "== verify =="
fail=0
for t in apktool apksigner zipalign keytool java python3 7z node npm; do
  if command -v "$t" >/dev/null 2>&1; then
    printf '  ok   %-10s %s\n' "$t" "$(command -v "$t")"
  else
    printf '  MISS %-10s\n' "$t"; fail=1
  fi
done
# asar is optional: both patchers fall back to `npx --yes @electron/asar`
if command -v asar >/dev/null 2>&1; then
  printf '  ok   %-10s %s\n' asar "$(command -v asar)"
else
  printf '  soft %-10s not on PATH (npx fallback will be used)\n' asar
fi

apktool --version 2>/dev/null | sed 's/^/  apktool /'
java -version 2>&1 | head -1 | sed 's/^/  /'
python3 -V | sed 's/^/  /'
echo "  node $(node -v 2>/dev/null)  npm $(npm -v 2>/dev/null)"
exit "$fail"
