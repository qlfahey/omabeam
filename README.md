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

Omarchy / Arch:

```bash
git clone https://github.com/qlfahey/omabeam.git
cd omabeam
./install-omarchy
```

Dependencies: `python`, `grim`, `ydotool`, `wtype`, `hyprland`, `jq`.
Optional: `cloudflared` (for the tunnel), an `omaspaces` install (for layouts).

One-time input setup (so touch and keyboard reach the desktop): add a udev rule
so `ydotoold` can use `/dev/uinput`, and make sure your user is in the `input`
group. The installer prints the exact commands.

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

## License

MIT. See [LICENSE](LICENSE).

Not affiliated with Omarchy; a community tool in the spirit of "build your own
OS."
