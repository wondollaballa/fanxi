# launcher/

The Fanxi Launcher: Python 3.9+ and Tkinter, no third-party Python packages.

```bash
./fanxi-launcher                 # from this folder
./fanxi-launcher --check
./fanxi-launcher --api http://192.0.2.10:8080
python3 build_app.py             # macOS: ../build/Fanxi Launcher.app
python3 build_app.py --desktop   # Linux: ../build/Fanxi Launcher.desktop
python3 -m unittest discover -s tests -v
```

Settings live in `launcher.json` under the Fanxi data folder (mode 0600). The launcher stores the
API token, never the password, and builds `host64` with `tools/build_posix.py` from the player's
own game files. See [docs/launcher.md](../docs/launcher.md).
