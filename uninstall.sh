#!/bin/sh
# Reverts the local helper installation; never touches servers or router.
set -eu
if [ "$(id -u)" != 0 ]; then
    echo 'Usage: sudo ./uninstall.sh' >&2
    exit 1
fi
HELPER=/Library/PrivilegedHelperTools/awg-home/awg_home_helper.py
if [ -f "$HELPER" ]; then
    /usr/bin/python3 "$HELPER" stop
fi
rm -f '/Library/Application Support/AWG Home/client.conf'
rmdir '/Library/Application Support/AWG Home' 2>/dev/null || true
rm -f /Library/PrivilegedHelperTools/awg-home/awg \
      /Library/PrivilegedHelperTools/awg-home/amneziawg-go \
      /Library/PrivilegedHelperTools/awg-home/awg_home_helper.py
rmdir /Library/PrivilegedHelperTools/awg-home 2>/dev/null || true
echo 'AWG Home helper removed. The app bundle is unchanged.'
