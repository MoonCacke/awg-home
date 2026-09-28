#!/bin/sh
# Installs only local Mac files. It does not start a VPN or change routes.
set -eu
if [ "$(id -u)" != 0 ] || [ "$#" -ne 1 ]; then
    echo 'Usage: sudo ./install.sh /absolute/path/to/client.conf' >&2
    exit 1
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROFILE=$1
case "$PROFILE" in
    /*) ;;
    *) echo 'Use an absolute profile path' >&2; exit 1 ;;
esac
if [ ! -f "$PROFILE" ] || [ -L "$PROFILE" ]; then
    echo 'Profile is missing or is a symlink' >&2
    exit 1
fi
if [ ! -f "$ROOT/build/AWG Home.app/Contents/Resources/awg" ]; then
    echo 'Build the app first with ./build.sh' >&2
    exit 1
fi
if [ -e /var/run/awg-home/state.json ]; then
    echo 'Disconnect AWG Home before reinstalling' >&2
    exit 1
fi
if [ ! -x /Applications/AmneziaVPN.app/Contents/MacOS/amneziawg-go ]; then
    echo 'AmneziaVPN engine is not installed in /Applications' >&2
    exit 1
fi
/usr/bin/install -d -o root -g wheel -m 755 /Library/PrivilegedHelperTools/awg-home
/usr/bin/install -d -o root -g wheel -m 700 '/Library/Application Support/AWG Home'
/usr/bin/install -o root -g wheel -m 755 \
    "$ROOT/build/AWG Home.app/Contents/Resources/awg_home_helper.py" \
    /Library/PrivilegedHelperTools/awg-home/awg_home_helper.py
/usr/bin/install -o root -g wheel -m 755 \
    "$ROOT/build/AWG Home.app/Contents/Resources/awg" \
    /Library/PrivilegedHelperTools/awg-home/awg
/usr/bin/install -o root -g wheel -m 755 \
    /Applications/AmneziaVPN.app/Contents/MacOS/amneziawg-go \
    /Library/PrivilegedHelperTools/awg-home/amneziawg-go
/usr/bin/install -o root -g wheel -m 600 "$PROFILE" \
    '/Library/Application Support/AWG Home/client.conf'
echo 'AWG Home helper installed. No VPN connection was started.'
