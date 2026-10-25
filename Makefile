PYTHON ?= python3
NPM ?= npm

.PHONY: help test server launcher init app check clean nav

help:
	@echo "make test      run the server and launcher tests"
	@echo "make server    run the Fanxi server"
	@echo "make launcher  run the Fanxi Launcher"
	@echo "make init      create the database and an administrator"
	@echo "make app       build the launcher bundle for this OS"
	@echo "make check     configuration, types and health overview"
	@echo "make nav       build walkable zone grids for every zone with monsters"
	@echo "make clean     remove build products (keeps data/)"

test:
	./scripts/test.sh

server:
	./scripts/server.sh

launcher:
	./scripts/launcher.sh

init:
	./scripts/init.sh

app:
	cd launcher-rs && $(NPM) run tauri build

nav:
	PYTHONPATH=server FANXI_GAME_DIR="$$FANXI_GAME_DIR" $(PYTHON) -m fanxi_server nav --all

check:
	cd server && $(PYTHON) -m fanxi_server doctor
	cd launcher-rs && $(NPM) run check

clean:
	rm -rf build .venv
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
