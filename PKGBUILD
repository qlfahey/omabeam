# Maintainer: qlfahey
pkgname=omabeam
pkgver=0.1.0
pkgrel=1
pkgdesc="Your Omarchy desktop, on your phone — a live phone bridge for Omarchy (Hyprland)"
arch=('any')
url="https://github.com/qlfahey/omabeam"
license=('MIT')
depends=('python' 'grim' 'ydotool' 'wtype' 'hyprland' 'jq')
optdepends=('cloudflared: public URL via a Cloudflare tunnel (omabeam tunnel)'
            'qrencode: show a scan-to-open QR code in the terminal'
            'omaspaces: open and save workspace layouts from the phone')
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  cd "$srcdir/$pkgname-$pkgver"
  install -Dm755 bin/omabeam "$pkgdir/usr/bin/omabeam"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
  install -Dm644 share/omabeam-server.py "$pkgdir/usr/share/omabeam/omabeam-server.py"
  install -Dm644 share/phone.html "$pkgdir/usr/share/omabeam/phone.html"
  install -Dm644 omabeam.desktop "$pkgdir/usr/share/applications/omabeam.desktop"
}
