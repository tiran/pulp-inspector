IMAGE ?= pulp-inspector
TAG ?= latest
PORT ?= 9090
CONTAINER_ENGINE ?= podman

.PHONY: dist build run clean

dist:
	uv build --no-cache --wheel --out-dir dist
	uv export --no-dev --no-editable --no-header --no-emit-project --no-hashes > dist/requirements.txt

build: dist
	$(CONTAINER_ENGINE) build -t $(IMAGE):$(TAG) -f Containerfile .

run: build
	$(CONTAINER_ENGINE) run --rm -p $(PORT):9090 $(IMAGE):$(TAG)

clean:
	rm -rf dist
	$(CONTAINER_ENGINE) rmi $(IMAGE):$(TAG) 2>/dev/null || true
