# git-lfs-nextcloud

Store [Git Large File Storage](https://git-lfs.com) (LFS) objects on your [LSTM Nextcloud](http://nextcloud.lstmed.ac.uk/) instead of [GitHub's LFS storage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage). Large files (`.dta`, `.rds`) are kept as tiny pointer files in Git; the actual binaries live on Nextcloud over [WebDAV](https://en.wikipedia.org/wiki/WebDAV).

```
Your Machine          GitHub              Nextcloud
────────────          ──────              ─────────
git push ──► pointer ──► repo            binary ──► /LFS/your-project/<oid[0:2]>/<oid[2:4]>/<full-oid>
             (text)       (code+pointers)           (via WebDAV)
```

## Prerequisites

- Python ≥ 3.10 + [Poetry](https://python-poetry.org/docs/#installation)
- R ≥ 4.1 + [renv](https://rstudio.github.io/renv/) (`install.packages("renv")`)
- [git-lfs](https://git-lfs.com/) (`brew install git-lfs` / `apt install git-lfs`)
- Access to a Nextcloud instance where you can create an App Password

## Setup

### 1. Install dependencies

```bash
# LFS transfer agent (Python)
poetry install

# R packages
Rscript -e "renv::restore()"
```

### 2. Create a Nextcloud App Password

In Nextcloud: **Personal Info → Settings → Security → Devices & Sessions → Create new app password**

Never use your main password here.

### 3. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with your values:

```ini
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_USER=your_username
NEXTCLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
NEXTCLOUD_LFS_PATH=LFS/your-project   # folder path inside Nextcloud
```

### 4. Register the custom transfer agent in your local git config

Git LFS 3.x ignores custom transfer agent settings in `.lfsconfig` for security reasons. You must add them to your local `.git/config` once after cloning:

```bash
git config lfs.standalonetransferagent nextcloud-agent
git config lfs.customtransfer.nextcloud-agent.path "$(poetry env info --path)/bin/python3"
git config lfs.customtransfer.nextcloud-agent.args lfs-nextcloud-agent.py
```

> **Why not `.lfsconfig`?** Since git-lfs 3.x, keys that can execute arbitrary code (`standalonetransferagent`, `customtransfer.*`) are rejected from the repo-level `.lfsconfig` — only user-level or local `.git/config` is trusted. The `.lfsconfig` in this repo documents the intended settings but they are ignored at runtime.

### 5. Pull LFS files

```bash
git lfs pull
```

This downloads all tracked large files from Nextcloud into your working tree.

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

Agent debug output (upload/download progress) is written to stderr and visible in your terminal during `git push`/`git pull`.

## How it works

Git LFS is configured to delegate all transfers to `lfs-nextcloud-agent.py` instead of the default HTTPS transfer. The intended settings live in `.lfsconfig` for documentation, but must be copied into `.git/config` locally (see Setup step 4) because git-lfs 3.x rejects executable-code keys from repo-level config. The agent speaks the [LFS custom transfer protocol](https://github.com/git-lfs/git-lfs/blob/main/docs/custom-transfers.md) over stdin/stdout and stores objects under:

```
<NEXTCLOUD_LFS_PATH>/<oid[0:2]>/<oid[2:4]>/<full-oid>
```

mirroring Git LFS's own internal layout.
