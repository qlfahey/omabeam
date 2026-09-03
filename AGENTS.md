# AGENTS.md — operating omabeam

Instructions for an AI agent (or a person) working in a fresh clone of this repo.
omabeam turns a phone into a live remote for an Omarchy / Hyprland desktop. This
file is how to set it up and answer the common requests without guessing.

## Requirements
- Omarchy or a Hyprland Wayland session (omabeam auto-detects the compositor's
  dispatch API — Omarchy's Lua `hl.dsp` or stock Hyprland's classic dispatchers).
- Commands: `python`, `grim`, `ydotool`, `wtype`, `hyprland`, `jq`.
- Optional: `cloudflared` (public link — auto-fetched on first use), `qrencode`
  (terminal QR), `omaspaces` (workspace layouts on the phone).

## Set it up (fresh clone)
```bash
./install-omarchy      # resolves deps, installs to ~/.local, sets up input access
omabeam doctor         # verify everything is ready (deps, uinput, group, dispatch)
omabeam                # start + print a link and QR to scan on the phone
```
`install-omarchy` needs **sudo once** for input access (a `/dev/uinput` udev rule
and adding the user to the `input` group) — the user must supply the sudo password,
and then **log out and back in once** for the group to take effect. If `omabeam
doctor` shows input isn't ready, that logout is almost always why. Nothing runs as
root except that one-time input setup.

## Handling common requests
| The user asks… | Do this |
|---|---|
| "set up omabeam" | `./install-omarchy`, then `omabeam doctor`; if input fails, walk them through the sudo rule + `input` group + logout. |
| "connect my phone" / "run it" | `omabeam` (link works anywhere) or `omabeam lan` (local network only). Have them scan the QR. |
| "input/keyboard isn't working" | `omabeam doctor` → fix whatever's ✗ (usually `/dev/uinput` perms, `input` group + logout, or `ydotoold`). |
| "give me a permanent link" | `omabeam setup` (ngrok free domain or a Cloudflare tunnel). Non-interactive: `NGROK_AUTHTOKEN=… NGROK_DOMAIN=… omabeam setup`, or `CF_API_TOKEN=… CF_ZONE=… omabeam setup`. |
| "the link changed again" | Expected for free quick-tunnels; use `omabeam setup` for a stable URL, or keep omabeam running. |
| "revoke / it might have leaked" | `omabeam rotate` (new token, kills every old link). |
| "stop it" | `omabeam stop`. |

## How it works (for debugging)
A small Python server (`share/omabeam-server.py`) streams the screen with `grim`
(MJPEG), reads window/workspace state from `hyprctl`, and turns touches/keys into
real input via `ydotool`/`wtype`. Cursor positioning uses the compositor's own move
dispatcher (exact, no calibration). The menu is parsed from Omarchy's own
`omarchy-menu.jsonc` and run with the same commands. `bin/omabeam` is the launcher;
`share/phone.html` is the phone UI.

## Security (state this when relevant)
The link carries a token — treat it like a password. A public tunnel is reachable
from anywhere while it runs and terminates TLS at the provider, so prefer `omabeam
lan` when on the same network, and `omabeam rotate` when done. Do not implement or
suggest weakening this.
