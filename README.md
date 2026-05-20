# git-lfs-nextcloud

Store [Git Large File Storage](https://git-lfs.com) (LFS) objects on your [LSTM Nextcloud](http://nextcloud.lstmed.ac.uk/) instead of [GitHub's LFS storage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage). Large files (`.dta`, `.rds`) are kept as tiny pointer files in Git; the actual binaries live on Nextcloud over [WebDAV](https://en.wikipedia.org/wiki/WebDAV).

```
Your Machine          GitHub              Nextcloud
────────────          ──────              ─────────
git push ──► pointer ──► repo            binary ──► /LFS/your-project/<oid[0:2]>/<oid[2:4]>/<full-oid>
             (text)       (code+pointers)           (via WebDAV)
```

> **Windows users:** read the Windows-specific notes in each section below.
> All setup commands must be run in **Git Bash** (the terminal that ships with
> Git for Windows), not PowerShell or CMD, unless a PowerShell alternative is
> explicitly shown. After setup is complete, RStudio's normal Git pane
> (commit / push / pull) works without any further changes.

## Prerequisites

- Python ≥ 3.10 + [Poetry](https://python-poetry.org/docs/#installation)
  - *macOS / Linux:* follow the [Poetry install docs](https://python-poetry.org/docs/#installation) or `pipx install poetry`
  - *Windows:* install Python from [python.org](https://www.python.org/downloads/) (tick **"Add python.exe to PATH"** during install), then install Poetry in PowerShell:
    ```powershell
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
    ```
    Restart Git Bash after installation so the `poetry` command is on the path.
- R ≥ 4.1 + [renv](https://rstudio.github.io/renv/) (`install.packages("renv")`)
- [git-lfs](https://git-lfs.com/)
  - *macOS:* `brew install git-lfs`
  - *Linux:* `apt install git-lfs` (or distro equivalent)
  - *Windows:* already bundled with [Git for Windows](https://git-scm.com/) — no separate install needed.
- Access to a Nextcloud instance where you can create an App Password
- *Windows + RStudio users:* configure RStudio's built-in terminal to use Git Bash: **Tools → Global Options → Terminal → New terminals open with: Git Bash**. All commands below must be run in that Terminal tab (not the Git pane).

## Setup

### 1. Install dependencies

```bash
# LFS transfer agent (Python)
poetry install

# R packages
Rscript -e "renv::restore()"
```

> **Windows:** run these commands in the **Terminal tab** of RStudio (or any Git Bash window), not in PowerShell. `poetry install` will create a virtual environment automatically.

### 2. Create a Nextcloud App Password

In Nextcloud: **Personal Info → Settings → Security → Devices & Sessions → Create new app password**

Never use your main password here.

### 3. Configure credentials

```bash
cp .env.example .env
```

> **Windows alternatives if `cp` is unfamiliar:**
> - In RStudio's **Files pane**, navigate to the project folder, tick `.env.example`, click **More → Copy**, then rename the copy to `.env`.
> - Or in File Explorer: copy `.env.example` and paste it as `.env` in the same folder.

Edit `.env` with your values:

```ini
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_USER=your_username
NEXTCLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
NEXTCLOUD_LFS_PATH=LFS/your-project   # folder path inside Nextcloud
```

### 4. Register the custom transfer agent in your local git config

Run these commands once after cloning, in **Git Bash** or RStudio's **Terminal tab**:

```bash
git config lfs.standalonetransferagent nextcloud-agent
git config lfs.customtransfer.nextcloud-agent.args lfs-nextcloud-agent.py
```

For the `path` key the command differs by platform — the Python executable lives in a different subfolder of the Poetry virtual environment:

**macOS / Linux:**
```bash
git config lfs.customtransfer.nextcloud-agent.path \
  "$(poetry env info --path)/bin/python3"
```

**Windows** (Git Bash or RStudio Terminal):
```bash
git config lfs.customtransfer.nextcloud-agent.path \
  "$(poetry env info --path)/Scripts/python.exe"
```

> **Why the full path?** git-lfs spawns the agent as a subprocess outside any active shell environment, so `python3` alone would not be found and the `requests` library (installed in the venv) would be unavailable. The `$(poetry env info --path)` subshell call expands to the venv root at the time you run the command, writing an absolute path into `.git/config`.

### 5. Install Git LFS extension

```
git lfs install  
Updated Git hooks.
Git LFS initialized.
```

### 6. Pull LFS files

```bash
git lfs pull
```

This downloads all tracked large files from Nextcloud into your working tree.

## Using RStudio after setup

Once the steps above are complete, RStudio's Git pane works normally — **no extra configuration is needed for day-to-day use**.

- **Commit, push, pull** via the Git pane as usual. When you click *Push*, RStudio calls `git push` under the hood, which invokes git-lfs, which reads `.git/config` and spawns the transfer agent automatically.
- **Agent output** (upload/download progress, prefixed `[nextcloud-agent]`) appears in the **Terminal tab**, not in the Git pane pop-up. If a push or pull seems to hang, switch to the Terminal tab to see what the agent is doing.
- **`git lfs pull`** (to download LFS files after cloning, or after a colleague pushes new large files) must be run in the **Terminal tab**:
  ```bash
  git lfs pull
  ```
- The RStudio **Console** tab (where R runs) is separate from the Terminal and cannot run git commands — use the Terminal tab for all git/lfs commands.

## Running the simulation

```bash
# Default: seed=42, n=50,000 individuals, 365 days (~30 MB output)
Rscript code/simulate.R

# Custom parameters
Rscript code/simulate.R <seed> <n_individuals> <timesteps>
Rscript code/simulate.R 123 100000 730
```

Output is written to `outputs/simulations/sim_<date>_seed<N>_n<N>_t<N>.dta` and automatically tracked by Git LFS.

## Daily workflow

```bash
# Run simulation, then commit
Rscript code/simulate.R
git add outputs/simulations/sim_*.dta
git commit -m "sim: seed=42, pop=50000, timesteps=365"
git push   # pointer → GitHub, binary → Nextcloud
```

`git pull` / `git lfs pull` work the same way in reverse.

## Verifying

```bash
# See which files LFS is managing
git lfs ls-files

# Confirm a file landed on Nextcloud
curl -u $NEXTCLOUD_USER:$NEXTCLOUD_APP_PASSWORD \
  $NEXTCLOUD_URL/remote.php/dav/files/$NEXTCLOUD_USER/$NEXTCLOUD_LFS_PATH/ \
  -X PROPFIND | grep -o '<d:href>[^<]*</d:href>'
```

> **Windows:** run the `curl` command above in Git Bash. Alternatively, in PowerShell:
> ```powershell
> $creds = [Convert]::ToBase64String(
>   [Text.Encoding]::ASCII.GetBytes("$env:NEXTCLOUD_USER`:$env:NEXTCLOUD_APP_PASSWORD"))
> Invoke-WebRequest `
>   -Uri "$env:NEXTCLOUD_URL/remote.php/dav/files/$env:NEXTCLOUD_USER/$env:NEXTCLOUD_LFS_PATH/" `
>   -Method PROPFIND `
>   -Headers @{Authorization="Basic $creds"} |
>   Select-Object -ExpandProperty Content
> ```

Agent debug output (upload/download progress) is written to stderr and visible in your terminal during `git push`/`git pull`.

## How it works

Git LFS is configured to delegate all transfers to `lfs-nextcloud-agent.py` instead of the default HTTPS transfer. The intended settings live in `.lfsconfig` for documentation, but must be copied into `.git/config` locally (see Setup step 4) because git-lfs 3.x rejects executable-code keys from repo-level config. The agent speaks the [LFS custom transfer protocol](https://github.com/git-lfs/git-lfs/blob/main/docs/custom-transfers.md) over stdin/stdout and stores objects under:

```
<NEXTCLOUD_LFS_PATH>/<oid[0:2]>/<oid[2:4]>/<full-oid>
```

mirroring Git LFS's own internal layout.
