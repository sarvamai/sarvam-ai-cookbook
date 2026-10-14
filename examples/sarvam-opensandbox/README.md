# Sarvam + OpenSandbox

Use Sarvam's `sarvam-m` to generate Python from a natural-language task, then execute that Python safely inside [Alibaba's OpenSandbox](https://github.com/alibaba/OpenSandbox) — a Docker-isolated runtime designed for AI-agent workloads.

The runner does a two-turn loop:

1. **Sarvam writes code** for the task.
2. **OpenSandbox runs it** in a fresh container (no host access).
3. **Sarvam reads the result** and produces a natural-language answer.

Running model-generated code inside a sandbox instead of `exec()`-ing it on the host is the same pattern Claude Code, Open Interpreter, and similar agents use — OpenSandbox is the execution backend.

## Prerequisites

- **Docker** running locally — OpenSandbox launches each execution as a container.
- **Python 3.10+**
- A **Sarvam API key** — get one at the [Sarvam Dashboard](https://dashboard.sarvam.ai/).
- The [`uv`](https://github.com/astral-sh/uv) CLI (recommended by OpenSandbox for launching the server).

## Validate end-to-end

Every action is its own step. You'll need **two terminals** — one for the OpenSandbox server (Steps 4–6), one for the runner (Steps 7–11).

### Step 1 — confirm Docker is running

```bash
docker ps
```

You should see a (possibly empty) container list, not an error. If you get `Cannot connect to the Docker daemon`, start Docker Desktop and re-run this.

### Step 2 — confirm `uv` is installed

```bash
uv --version
```

If missing, install it (macOS): `brew install uv`. Other platforms: [astral.sh/uv](https://github.com/astral-sh/uv#installation).

### Step 3 — pre-pull the code-interpreter image

```bash
docker pull sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.0.2
```

The image lives on Alibaba Cloud's `cn-zhangjiakou` registry. Pulls from outside China take a while, and if you skip this step the runner's first call will time out trying to pull on-demand. Doing it upfront avoids that. (If you mirror the image to a faster registry, pull from there instead and set `SANDBOX_IMAGE` in Step 9.)

### Step 4 — generate the OpenSandbox config

```bash
uvx opensandbox-server init-config ~/.sandbox.toml --example docker
```

Expected: `Wrote example config (docker) to /Users/<you>/.sandbox.toml`.

### Step 5 — start the OpenSandbox server (Terminal 1)

```bash
export DOCKER_HOST=unix://$HOME/.docker/run/docker.sock   # Docker Desktop on macOS
export OPENSANDBOX_INSECURE_SERVER=YES                    # local dev only; see note below
uvx opensandbox-server
```

Leave this terminal running. You should see `Uvicorn running on http://127.0.0.1:8080`.

> **Why `DOCKER_HOST`?** The Python `docker` client OpenSandbox uses defaults to `/var/run/docker.sock`. Docker Desktop on macOS puts its socket under `~/.docker/run/docker.sock`, so it needs to be pointed there. Linux installs that ship the socket at `/var/run/docker.sock` can skip this export.
>
> **Why `OPENSANDBOX_INSECURE_SERVER=YES`?** The server refuses to start non-interactively when `server.api_key` is unset in `~/.sandbox.toml`. For local dev, this env var acknowledges that the proxy is unauthenticated. For anything beyond a single-machine demo, set a real key in the TOML file and drop this env var.

### Step 6 — confirm the server is listening (new shell)

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

You should see one line with a `Python` process listening on `127.0.0.1:8080`. If the command prints nothing, the server didn't bind — check Terminal 1's logs.

### Step 7 — create the runner virtualenv (Terminal 2)

```bash
cd examples/sarvam-opensandbox
python3 -m venv .venv
```

### Step 8 — install the runner dependencies

```bash
.venv/bin/pip install -r requirements.txt
```

### Step 9 — export your Sarvam key

```bash
export SARVAM_API_KEY=your_sarvam_key
```

Optional overrides (only if your server isn't on the default):

```bash
# export SANDBOX_DOMAIN=localhost:8080
# export SANDBOX_API_KEY=...                               # match server.api_key from ~/.sandbox.toml
# export SANDBOX_IMAGE=your.registry/opensandbox/code-interpreter:v1.0.2
```

### Step 10 — run the example

```bash
.venv/bin/python code_runner.py "List the first 10 prime numbers."
```

Expected output (verbatim from a real run):

```
Task: List the first 10 prime numbers.

=== Turn 1: Sarvam writes code ===
def is_prime(n):
    if n <= 1:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

primes = []
num = 2
while len(primes) < 10:
    if is_prime(num):
        primes.append(num)
    num += 1

print(primes)

=== Sandbox execution ===
[2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

=== Turn 2: Sarvam explains the result ===
The first 10 prime numbers are 2, 3, 5, 7, 11, 13, 17, 19, 23, and 29.
```

### Step 11 — stop the server

`Ctrl+C` in Terminal 1. (Or, if it's detached: `pkill -f opensandbox-server`.)

## How it works

[`code_runner.py`](code_runner.py) is ~100 lines:

- `ask_sarvam(...)` — calls Sarvam's `sarvam-m` via the OpenAI-compatible endpoint at `https://api.sarvam.ai/v1`. Strips the `<think>...</think>` reasoning prefix the model emits.
- `extract_python(...)` — pulls the code out of the ```` ```python ... ``` ```` fence Sarvam returns.
- `run_in_sandbox(...)` — creates an OpenSandbox `Sandbox`, opens a `CodeInterpreter`, runs the code, returns stdout (or the error). The sandbox is killed in a `finally` block so containers don't leak if the script crashes.

The two Sarvam calls use different system prompts: one asks for code only, one asks for a plain-language explanation given the stdout.

## Notes & limitations

- **Sandbox network access.** The default code-interpreter image runs without network. Tasks that need `requests` or external APIs will fail unless you use a different image or configure egress in `~/.sandbox.toml`.
- **No retry on error.** If the generated code crashes, the runner prints the error and Sarvam will summarise the failure — it does not feed the error back and try again. Adding a retry loop is a natural next extension.
- **`<think>` blocks.** `sarvam-m` is a reasoning model; its raw output includes a `<think>...</think>` block that we strip before parsing. If you swap to a different model, you can drop `strip_think()`.

## Links

- [OpenSandbox on GitHub](https://github.com/alibaba/OpenSandbox)
- [OpenSandbox `code-interpreter` example](https://github.com/alibaba/OpenSandbox/tree/main/examples/code-interpreter)
- [Sarvam AI Documentation](https://docs.sarvam.ai/)
