# Variables
VENV=.venv
PYTHON=$(VENV)/Scripts/python.exe
PIP=$(VENV)/Scripts/pip.exe
ACTIVATE=$(VENV)/Scripts/activate.bat

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
	$(ACTIVATE)

install:
	$(PIP) install -r requirements.txt

lint:
	$(VENV)/Scripts/flake8 src/

test:
	$(PYTHON) -m unittest discover test -p "*_tests.py"

clean:
	rm -rf *.pyc __pycache__ build/ dist/

build: clean
	pyinstaller --noconfirm --onefile --name "aoe_rec_tools" src/aoe_rec_tools.py
