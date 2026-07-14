IMAGE ?= pulp-inspector
TAG ?= latest
PORT ?= 9090
CONTAINER_ENGINE ?= podman

.PHONY: build run clean

build:
	$(CONTAINER_ENGINE) build -t $(IMAGE):$(TAG) -f Containerfile .

run: build
	$(CONTAINER_ENGINE) run --rm -p $(PORT):9090 $(IMAGE):$(TAG)

clean:
	$(CONTAINER_ENGINE) rmi $(IMAGE):$(TAG)
