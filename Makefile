.PHONY: install

install: dev-requirements.txt requirements.txt
	pip-sync requirements.txt dev-requirements.txt

dev-requirements.txt: dev-requirements.in requirements.txt
	pip-compile dev-requirements.in --generate-hashes

requirements.txt: requirements.in
	pip-compile requirements.in --generate-hashes
