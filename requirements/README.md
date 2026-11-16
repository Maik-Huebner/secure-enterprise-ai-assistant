# Dependency lock strategy

`lock-py313.txt` is the exact transitive environment used by CI and the container for Python 3.13.
The project metadata also constrains every direct runtime and development dependency. Install the
lock first and then install the project non-editably with `--no-deps --no-build-isolation`.

PyTorch should be installed from its official CPU wheel index before the lock on Linux CI or in
the container. The local-version CPU wheel satisfies the pinned public version without installing
unused CUDA runtime packages.

Release v1.1.0 officially supports Python `>=3.13,<3.14`. Python 3.13.9 plus this lock is the
reproducibly validated runtime used by the release gate, CI, Fresh-Clone validation, and Docker.
Earlier Python versions are not claimed as supported until they pass equivalent lock-level
validation.

## Refreshing the lock

Resolve from `pyproject.toml` with `uv`, targeting macOS 14 on arm64. That target keeps CUDA
packages out of the lock; Linux uses the CPU PyTorch wheel installed beforehand. `uv` keeps every
version already present in the output file unless a package is named with `--upgrade-package`,
so the diff stays limited to intended changes:

```bash
MACOSX_DEPLOYMENT_TARGET=14.0 uv pip compile pyproject.toml --extra dev \
  --python-version 3.13 --python-platform aarch64-apple-darwin \
  --no-annotate --no-header \
  --upgrade-package <name> \
  -o requirements/lock-py313.txt
```

Then restore the two header comment lines, review the diff, install the lock in a fresh virtual
environment, and run every Make target (including `make deps-audit`) plus the wheel smoke test.
Do not hand-edit individual transitive versions without repeating that validation.

## Known exceptions

`make deps-audit` ignores four advisory IDs for `chromadb`. The package arrives only through
CrewAI, is not imported by this project, and has no fixed release. The exception is removed when
CrewAI is replaced in v2 work package 4.

Pydantic stays below 2.13 because CrewAI 1.15.41 requires `pydantic<2.13`.
