# omabeam

**Your Omarchy desktop, on your phone.**

![omabeam](docs/hero.png)

omabeam turns any phone into a live remote for an Omarchy machine: see your
workspaces, open a window as a full-screen tile, drive the whole desktop by
touch, and reach the entire Omarchy menu — themes, backgrounds, settings,
system — from the same screen. It renders in your current theme and font, so
it feels like the desktop, not a web page.

## What it does

- **Workspaces** — switch spaces, see what's on each one by window title.
- **Windows** — tap a window to open it as a portrait tile you can tap, scroll,
  and type into; move it to another space or close it from the phone.
- **Full control** — drive the entire live desktop by touch, with an on-screen
  keyboard that has Ctrl / Alt / Super for any Hyprland keybinding.
- **The Omarchy menu** — the real menu (Apps, Learn, Trigger, Style, Setup,
  Install, Remove, Update, System), parsed from your own menu files and run with
  the same commands. Themes and backgrounds apply straight from the phone.

## Screens

| Home | Menu | Window tile |
|---|---|---|
| ![home](docs/overview.png) | ![menu](docs/menu.png) | ![tile](docs/tile.png) |

## Works with omaspaces

[omaspaces](https://github.com/qlfahey/omaspaces) is a separate tool — a window
layout builder and dock for Omarchy. If it's installed, omabeam adds a **Spaces**
section that opens and saves your omaspaces layouts. omabeam works fine without
it; the section just won't appear.

## Install

Omarchy / Arch — the installer resolves dependencies, installs into `~/.local`
(no root for the app itself), and sets up input access:

```bash
git clone https://github.com/qlfahey/omabeam.git
cd omabeam
./install-omarchy
```

**Prebuilt package** (installs system-wide, pulls dependencies):

```bash
sudo pacman -U https://github.com/qlfahey/omabeam/releases/download/v0.1.0/omabeam-0.1.0-1-any.pkg.tar.zst
```

Or build it yourself with `makepkg -si` (see [PKGBUILD](PKGBUILD)). AUR
submission is prepared (`./publish-aur.sh`) and coming soon.

Dependencies: `python`, `grim`, `ydotool`, `wtype`, `hyprland`, `jq`.
Optional: `cloudflared` (public URL), `qrencode` (terminal QR), `omaspaces` (layouts).

Input access is one-time: `ydotoold` needs `/dev/uinput` and your user must be in
the `input` group. `./install-omarchy` does this for you (a udev rule + group add;
log out and back in once). The prebuilt package prints the same steps.

## Use

```bash
omabeam            # start the server, print the LAN URL to open on your phone
omabeam tunnel     # also open a Cloudflare tunnel and print a public URL
omabeam url        # show the current URL
```

Open the printed URL on your phone (same Wi-Fi for the LAN URL, anywhere for the
tunnel). The URL carries a token; treat it like a password.

## How it works

A small Python server captures the screen with `grim` (streamed as MJPEG),
reports window and workspace state from `hyprctl`, and turns touches into real
input with `ydotool` and `wtype`. The menu is read from Omarchy's own
`omarchy-menu.jsonc` and executed with the same shell actions, so it always
matches the desktop.

## Security

omabeam gives whoever opens the URL full control of your desktop, so treat it
accordingly:

- The URL carries a **random token** (regenerated per session); every request is
  checked against it in constant time. **Treat the URL like a password** — don't
  share it or paste it where it gets logged.
- On the LAN, the server listens on your local network only. The **tunnel** makes
  it reachable from anywhere for as long as it runs — prefer the LAN URL for
  routine use, and stop the tunnel when you're done.
- The menu runs Omarchy's own commands (read from your menu files), not arbitrary
  input from the phone; touch and keys go through `ydotool`/`wtype`.

## License

MIT. See [LICENSE](LICENSE).

Not affiliated with Omarchy; a community tool in the spirit of "build your own
OS."
