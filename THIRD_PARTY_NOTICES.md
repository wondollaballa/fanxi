# Third-party notices

Fanxi is MIT-licensed (see [LICENSE](LICENSE)). It contains code derived from an earlier
MIT-licensed project. That project's copyright notice and license are reproduced below, as the
license requires.

## Upstream MIT notice

```
MIT License

Copyright (c) 2026 Joshua Tyree

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Vendored libraries

The client vendors the libraries it builds against. They keep their own licenses and copyright
notices in their folders under `third_party/`:

| Library | License | Folder |
|---|---|---|
| SDL 3 | zlib | `third_party/sdl3/` |
| mbedTLS | Apache-2.0 | `third_party/mbedtls/` |
| LuaJIT | MIT | `third_party/luajit/` |
| SQLite | public domain | `third_party/sqlite/` |
| Dear ImGui | MIT | `third_party/imgui/` |
| Font Awesome Free | CC BY 4.0 (icons), SIL OFL 1.1 (fonts), MIT (code) | `third_party/` / `assets/fonts/` |
| Capstone (build-time, not vendored) | BSD-3-Clause | installed into `.venv` |
| pefile (build-time, not vendored) | MIT | installed into `.venv` |

If a license file is missing from a vendored folder, the upstream project's license applies; see
that project's distribution.

## Game data

Fanxi ships no FINAL FANTASY XI data, binaries or assets extracted from the game. The client is
built on the player's machine from the player's own `FFXiMain.dll`, `FFXi.dll` and `ROM` folder.
`assets/` contains only Fanxi's own icons and UI art created for this project.

FINAL FANTASY XI and SQUARE ENIX are trademarks of Square Enix Holdings Co., Ltd. Fanxi is not
affiliated with or endorsed by Square Enix.
