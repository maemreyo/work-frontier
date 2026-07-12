# Work Frontier

Work Frontier is a standalone dependency-aware readiness control plane.

## Bootstrap

```sh
make bootstrap
make check-static
make test
```

The active baseline pins Python 3.13 through `uv` and the Control Room toolchain
through pnpm. Product architecture and runtime services are introduced only by
their dependency-ordered implementation todos.
