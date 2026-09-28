#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
make -C "$ROOT/vendor/amneziawg-tools/src" -j2
APP="$ROOT/build/AWG Home.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
clang -O2 -fobjc-arc -framework Cocoa \
  -o "$APP/Contents/MacOS/AWGHome" "$ROOT/src/main.m"
cp "$ROOT/src/Info.plist" "$APP/Contents/Info.plist"
cp "$ROOT/src/awg_home_helper.py" "$APP/Contents/Resources/awg_home_helper.py"
cp "$ROOT/vendor/amneziawg-tools/src/wg" "$APP/Contents/Resources/awg"
codesign --force --sign - "$APP"
printf '%s\n' "$APP"
