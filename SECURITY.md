# Security

Fanxi is a self-hosted game server and desktop client. Please treat the server as you would any
internet-facing service.

## Reporting a vulnerability

Once the repository has GitHub's private vulnerability reporting enabled, use **Security →
Advisories → Report a vulnerability**. Do not open a public issue for a vulnerability, and never
include passwords, tokens, private keys or player data in an issue.

Include:

- the version/commit and the component (launcher, HTTP API, game gateway, database);
- reproduction steps and the impact you believe it has;
- any logs with tokens, passwords and IP addresses redacted.

## Secrets

No secret belongs in this repository. In particular:

- passwords are stored only as PBKDF2 hashes;
- launcher tokens and launch tokens are stored only as SHA-256 hashes;
- the auth gateway's TLS certificate is generated into `data/tls/` (git-ignored);
- the admin key is `FANXI_ADMIN_KEY` or an `admin` account, never a checked-in default;
- the launcher stores its API token in a `0600` settings file and never stores the password.

If you find a committed credential, rotate it first, then remove it from the tree and from the
git history before publishing.

## Trust model

The launcher API is authenticated and rate-limited. The game protocol is the FINAL FANTASY XI
private-server protocol: the client asserts its position, the server has no anti-cheat, and the
auth port uses a self-signed certificate the client does not verify. Run the game gateway on a
network you trust, or behind a firewall/VPN. See [docs/architecture.md](docs/architecture.md) and
[docs/server.md](docs/server.md) for the full model and the hardening checklist.

## Supported versions

Security fixes land on `main`. Tagged releases are snapshots; run the newest release or `main`.
