# Pulp Inspector

Browse and inspect Python wheels hosted on Pulp Python indexes, such as the RHOAI indexes on [packages.redhat.com](https://packages.redhat.com/).

## Features

- **Browse indexes, packages, and wheels** -- navigate the index hierarchy, list packages per version/variant, and drill into individual wheel files.
- **Inspect wheel contents** -- list files inside a wheel without downloading it, using HTTP Range requests via [zipwire](https://pypi.org/project/zipwire/).
- **View file content** -- read text files (METADATA, LICENSE, Python sources) directly from the remote wheel.
- **ELF binary analysis** -- inspect shared objects (`.so` files) inside wheels with [elfdeps](https://pypi.org/project/elfdeps/): soname, dependencies, and runpath.
- **Compare with PyPI** -- compare a Pulp-hosted wheel against the upstream wheel on PyPI.org. Detects matching files, differences, Pulp-only files, PyPI-only files, and [fromager](https://pypi.org/project/fromager/) build artifacts. Includes inline unified diffs for changed text files.

## Quick start

```
pip install pulp-inspector
pulp-inspector --host 0.0.0.0 --port 9090
```

### Container

Run the pre-built image from GHCR:

```
podman run --rm -p 9090:9090 ghcr.io/tiran/pulp-inspector:latest
```

Or build locally:

```
make run
```

Then open <http://localhost:9090> in your browser.
