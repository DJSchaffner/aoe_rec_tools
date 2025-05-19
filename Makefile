# Variables
VENV=.venv
PYTHON=$(VENV)\Scripts\python.exe
PIP=$(VENV)\Scripts\pip.exe

# Default target
.PHONY: all help venv install lint clean

all: clean venv install lint

help:
	@echo Makefile commands:
	@echo   make venv      - Create virtual environment
	@echo   make install   - Install dependencies
	@echo   make lint      - Run lint checks \(flake8\)
	@echo   make clean     - Remove temporary files

venv:
	python -m venv $(VENV)

install:
	$(PIP) install -r requirements.txt

lint:
	$(VENV)\Scripts\flake8 src\

clean:
	rm -rf *.pyc __pycache__
