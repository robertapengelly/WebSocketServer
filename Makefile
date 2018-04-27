all: WebSocketServer

clean:
	rm -rf bin
	find . -name "*.pyc" -delete
	find . -name "*.class" -delete

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
PYTHON ?= /usr/bin/env python

install: WebSocketServer
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 bin/WebSocketServer $(DESTDIR)$(BINDIR)
	rm -rf bin

.PHONY: all clean install

WebSocketServer: WebSocketServer/*py
	mkdir -p zip
	for d in WebSocketServer; do \
	  mkdir -p zip/$$d; \
	  cp -pPR $$d/*.py zip/$$d/; \
	done
	touch -t 200001010101 zip/WebSocketServer/*.py
	cp __main__.py zip/
	cd zip; zip -q ../WebSocketServer WebSocketServer/*.py __main__.py
	rm -rf zip bin
	mkdir bin
	echo '#!$(PYTHON)' > bin/WebSocketServer
	cat WebSocketServer.zip >> bin/WebSocketServer
	rm WebSocketServer.zip
	chmod a+x bin/WebSocketServer
