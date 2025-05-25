# Variables
VENV=.venv
PYTHON=$(VENV)/Scripts/python
PIP=$(VENV)/Scripts/pip
FLAKE8=$(VENV)/Scripts/flake8

# Default target
.PHONY: all help venv install lint test clean build

all: clean install lint test build

help:
	@echo Makefile commands:
	@echo   make venv      - Create virtual environment
	@echo   make install   - Install dependencies
	@echo   make lint      - Run lint checks \(flake8\)
	@echo   make test      - Run unit tests
	@echo   make clean     - Remove temporary files
	@echo   make build     - Build into standalone executable

venv:
	python -m venv $(VENV)

install:
	$(PIP) install -r requirements.txt

lint:
	$(FLAKE8) src/

test:
	$(PYTHON) -m unittest discover test -p "*_tests.py"

clean:
	rm -rf *.pyc __pycache__ build/ dist/

build: clean
	$(PYTHON) -m pip install pyinstaller
	$(PYTHON) -m PyInstaller --noconfirm --onefile --name "aoe_rec_tools" src/aoe_rec_tools.py
