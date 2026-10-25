# server/

The Fanxi server: HTTP API for the launcher, plus the game gateway (auth, data, lobby,
search, zone).

```bash
cd server
python3 -m fanxi_server init
python3 -m fanxi_server create-admin
python3 -m fanxi_server run
python3 -m fanxi_server doctor
```

- Default API: `http://127.0.0.1:8080/api/v1`
- Default game ports: 54231/tcp (auth), 54230/tcp (data), 54001/tcp (lobby), 54002/tcp
  (search), 54230/udp (zone)
- Database: `../data/fanxi.db` (override with `FANXI_DB`)
- Navigation cache: `../data/nav/<zone>.nav`, built from the game folder's collision meshes
  (`FANXI_GAME_DIR`, or `FANXI_NAV_DIR` to move the cache). Build zones ahead of time with
  `python3 -m fanxi_server nav --zone 100 --zone 101` or `--all`; see
  [docs/world.md](../docs/world.md#zone-navigation).
- Configuration: `FANXI_*`; see [docs/server.md](../docs/server.md)
- Tests: `python3 -m unittest discover -s tests -v` from this folder, or
  `../scripts/test.sh` from the root.

The gateway needs the player's `res/compress.dat` (`FANXI_HUFFMAN` or `FANXI_GAME_DIR`). Without
it, the HTTP API still runs but the game cannot enter a zone.
