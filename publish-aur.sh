#!/usr/bin/env bash
# Publish omabeam to the AUR.
#
# Prerequisites (one time):
#   1. An AUR account at https://aur.archlinux.org
#   2. Your SSH public key added there (My Account → SSH Public Key)
#
# Usage: ./publish-aur.sh [pkgver]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
ver="${1:-$(sed -n 's/^pkgver=//p' "$here/PKGBUILD")}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone ssh://aur@aur.archlinux.org/omabeam.git "$tmp"
cp "$here/PKGBUILD" "$here/.SRCINFO" "$tmp/"
cd "$tmp"
git add PKGBUILD .SRCINFO
git commit -m "omabeam $ver"
git push
echo "✓ Published: https://aur.archlinux.org/packages/omabeam"
