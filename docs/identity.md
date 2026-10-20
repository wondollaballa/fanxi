# Identity

Fanxi is a clean identity built on top of an MIT-licensed codebase. This page records the names,
IDs and boundaries so future changes stay consistent.

## Names

| Context | Value |
|---|---|
| Product, window, docs | **Fanxi** |
| Executable / package | `fanxi`, `fanxi_launcher`, `fanxi_server` |
| Repository | `fanxi` |
| Server name (default) | `Fanxi` |
| Launcher window | `Fanxi Launcher` |
| Launcher version | `Fanxi Launcher 0.1.0` |
| API server header | `Fanxi/0.1.0` |
| Server tagline | FINAL FANTASY XI, on your own terms. |

The game's own title, **FINAL FANTASY XI**, stays as the game title in the window, bundle file
name target and documentation. Fanxi is the project around it.

## Identifiers

| Thing | Value |
|---|---|
| Launcher macOS bundle ID | `com.fanxi.launcher` |
| Game macOS bundle ID | `com.fanxi.game` |
| Android package | `com.fanxi.app` |
| Linux app id / desktop file | `fanxi`, `fanxi-launcher.desktop` |
| macOS data folder | `~/Library/Application Support/Fanxi` |
| Linux data folder | `$XDG_DATA_HOME/fanxi` or `~/.local/share/fanxi` |
| Windows data folder | `%APPDATA%\Fanxi` |
| Settings file | `launcher.json` inside the data folder |
| Log folder | `logs/` inside the data folder |
| Database | `data/fanxi.db` |
| TLS files | `data/tls/auth-cert.pem`, `auth-key.pem` |
| Environment prefix | `FANXI_*` (launcher/server); `FFXI_*` remains for game-client options |
| API path | `/api/v1` |
| Local port | `8080` HTTP, 54231/54230/54001 game |

`FFXI_*` environment variables in `host/` and `runtime/` configure the game itself (renderer,
addon host, replay). They are not project branding and are part of the client's existing
interface. New project-level settings use `FANXI_*`.

The client's wire protocol still uses the names the protocol has (`FFXI_LSB_SESSION`, JSON
`command`, `result`, and so on). Those are compatibility vocabulary with FINAL FANTASY XI
servers, not references to this repository.

## What was removed

The port deliberately removed every runtime reference to the previous project:

- product name, window titles and dialog titles;
- repository URLs, raw-content install URLs, release asset names and the old install command;
- macOS bundle identifiers, Linux app id/desktop file, Android package and app label;
- application-support/data and cache folder names;
- the macOS code-signing identity name;
- the old launcher, installer and screenshot/community banner references;
- the third-party rich-presence integration, including its hard-coded application ID, its source
  files, environment variables, build entries and documentation.

What remains:

- the MIT copyright notice, in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md), because the
  license requires it;
- the FINAL FANTASY XI game data, which the build reads from the player's own installation and
  never ships;
- protocol constants (Blowfish tables, view key, Huffman algorithm) and the Huffman table read
  from the player's `compress.dat`, because the client cannot speak to a server without them.

## Secrets

Nothing in the repository is a secret:

- no third-party application ID, bot token or webhook;
- no repository deploy key, signing certificate or release token;
- no default account, API key or database password;
- no game data, `compress.dat`, DATs or retail binaries.

Secrets are created locally and stay local:

| Secret | Where it lives |
|---|---|
| Admin API key | `FANXI_ADMIN_KEY` environment variable |
| Admin account password | `accounts.password_hash` (PBKDF2, salted) |
| Player password | same, never stored by the launcher |
| Launcher session | `api_sessions.token_hash` (SHA-256) + `launcher.json` (0600) on the player's machine |
| Game session | `game_sessions.session_hash` (random bytes) |
| TLS private key | `data/tls/auth-key.pem`, mode 0600, generated on first run |
| Database | `data/fanxi.db`; protect the file and backups |

## Voice

- Second person, plain sentences, no marketing superlatives.
- "Fanxi" is a proper noun; "the Fanxi server", "the Fanxi launcher".
- Avoid unexplained acronyms; the game is FINAL FANTASY XI, the project is Fanxi.
- Error messages say what happened and what to do next.
- Never call the project a fork, a reskin or a clone in user-facing text.

## Checklist for new strings

- [ ] User-facing names say Fanxi.
- [ ] Paths use the Fanxi data folder, not a previous one.
- [ ] New IDs are `com.fanxi.*` / `fanxi` / `fanxi-*`.
- [ ] New environment variables start with `FANXI_` (unless they configure the game client).
- [ ] No repository URL points at the old project.
- [ ] No key, token or certificate is committed.
- [ ] If code is copied from elsewhere, add its license to
      [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
