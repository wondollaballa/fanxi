PYTHON ?= python3

.PHONY: help test server launcher init app check clean

help:
	@echo "make test      run the server and launcher tests"
	@echo "make server    run the Fanxi server"
	@echo "make launcher  run the Fanxi Launcher"
	@echo "make init      create the database and an administrator"
	@echo "make app       build the launcher bundle for this OS"
	@echo "make check     configuration and health overview"
	@echo "make clean     remove build products (keeps data/)"

test:
	./scripts/test.sh

server:
	./scripts/server.sh

launcher:
	./launcher/fanxi-launcher

init:
	./scripts/init.sh

app:
	$(PYTHON) launcher/build_app.py

check:
	cd server && $(PYTHON) -m fanxi_server doctor
	./launcher/fanxi-launcher --check

clean:
	rm -rf build .venv
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
