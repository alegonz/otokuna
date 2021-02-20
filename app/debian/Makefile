VERSION:=0.1.0
GIT_DATE:=$(shell date -u +%Y%m%d -d @$(shell git show -s --format=%ct))
GIT_HASH:=$(shell git show -s --format=%h)
DEB_VERSION:=$(VERSION)~$(GIT_DATE)+$(GIT_HASH)

.PHONY: clean
clean:
	rm -rf pkg-build *.deb

.PHONY: deb
deb: clean
	go-bin-deb generate --version $(DEB_VERSION)
