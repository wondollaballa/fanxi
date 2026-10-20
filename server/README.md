# server/

The Fanxi server: HTTP API for the launcher, plus the game gateway (auth, data, lobby, zone).

```bash
cd server
python3 -m fanxi_server init
python3 -m fanxi_server create-admin
python3 -m fanxi_server run
python3 -m fanxi_server doctor
```

- Default API: `http://127.0.0.1:8080/api/v1`
- Default game ports: 54231/tcp (auth), 54230/tcp (data), 54001/tcp (lobby), 54230/udp (zone)
- Database: `../data/fanxi.db` (override with `FANXI_DB`)
- Configuration: `FANXI_*`; see [docs/server.md](../docs/server.md)
- Tests: `python3 -m unittest discover -s tests -v` from this folder, or
  `../scripts/test.sh` from the root.

The gateway needs the player's `res/compress.dat` (`FANXI_HUFFMAN` or `FANXI_GAME_DIR`). Without
it, the HTTP API still runs but the game cannot enter a zone.
