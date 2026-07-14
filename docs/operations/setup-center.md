# Setup Center Operations

Work Frontier provides one interactive setup and repair workflow across development and production. The supported first-run command is:

```sh
uv run work-frontier setup
```

The command binds a setup-only FastAPI process to `127.0.0.1` on an ephemeral port, creates a one-time session token, opens the browser, and serves packaged Setup Center assets. The token is kept in the URL fragment, exchanged once for an HttpOnly session cookie, and removed from browser history.

## Independent readiness

Setup does not collapse unrelated operational states into one “complete” flag.

### Local Runtime Ready

Covers the local toolchain, configuration, PostgreSQL, object storage, migrations, and fast checks. Development can enter the Control Room when this capability is ready even when release preparation is absent.

### GitHub Integration Ready

Covers GitHub identity, repository access, installation scope, and required permissions. Development prefers an existing GitHub CLI identity and stores a `gh-cli://` reference instead of copying the token. Production uses GitHub App machine identity separately from human OAuth/OIDC approval identity.

### Release Certification Ready

Covers a clean exact revision, isolated sandbox, signing-key reference, external harness dependencies, and the real soak policy. Setup Center prepares and invokes certification; it does not weaken exact-revision checks, shorten the soak, or turn placeholders into valid evidence.

### Production Cutover Ready

Covers approved change identity, exact source revision, parity evidence, one-writer fencing, observation, and rollback readiness. Setup Center never approves or activates cutover silently.

## Detect → Plan → Apply

1. **Detect** is read-only. It inspects tools, ports, Git state, service reachability, keyring availability, GitHub CLI identity, configuration revision, and interrupted setup sessions.
2. **Plan** is deterministic and secret-free. It lists files, references, services, commands, remote checks, risk, dependencies, reversibility, and explicit exclusions.
3. **Apply** journals every state transition before and after a side effect. Verified actions are not repeated on resume. Reversible actions compensate in reverse dependency order; irreversible outcomes become `manual_recovery_required` with exact guidance.

A changed configuration revision or detection snapshot invalidates the reviewed plan. Run detection again instead of bypassing the stale-plan guard.

## Secrets

Normal configuration stores references such as:

```text
keyring://work-frontier/release/signing-key
env://WF_DATABASE_PASSWORD
gh-cli://github.com/account-name
```

Plaintext secrets are never written to TOML, SQLite, logs, evidence, plan JSON, URLs, DOM output, or browser storage. A submitted secret is sent once to the loopback backend, stored by the configured provider, and cleared from the form. Headless environments use injected environment references.

## Ongoing repair

After first run, Setup remains available in Control Room. Operators can refresh readiness, detect drift, review a repair plan, apply it, and inspect redacted action results. Useful commands are:

```sh
uv run work-frontier setup status --json
uv run work-frontier setup repair
uv run work-frontier setup plan --repository owner/sandbox --json > setup-plan.json
uv run work-frontier setup apply --plan setup-plan.json --non-interactive
uv run work-frontier config show --redacted
```

## Verification

Run the focused setup suite with:

```sh
make test-setup
make check-setup-assets
```

Before release, also run the repository’s normal `make check` and `make verify`. Standard ReleaseCertification and production cutover remain separate exact-revision gates.
