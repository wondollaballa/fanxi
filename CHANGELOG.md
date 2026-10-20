# Changelog

## 0.1.0 — first Fanxi release

- Ported the native FINAL FANTASY XI client (recompiler, runtime, host, addon host) and rebranded
  it around Fanxi: new name, icons, bundle IDs, paths, window titles and documentation.
- Removed the previous launcher/installer references, third-party presence integration and its
  application ID, old repository URLs and keys.
- Added `launcher/`: a dependency-free Python/Tkinter desktop launcher with sign-in, character
  creation, server status, news, game-folder detection, `host64` building and Play.
- Added `server/`: a standard-library HTTP API (accounts, sessions, characters, launch tokens,
  news, releases, admin) and a game gateway (TLS auth, login data, lobby, zone).
- Added `database/`: SQLite migrations and seed data for accounts, characters, zones, news and
  settings.
- Added tests for the server (including a live TLS auth/lobby/zone handshake) and launcher.
- Added packaging: macOS `.app`, Linux desktop entry, `install.sh`, `setup.command`, development
  scripts and CI.
