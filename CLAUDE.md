# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

This is a **custom Git LFS transfer agent** that stores large files on Nextcloud (via WebDAV) instead of GitHub's LFS storage. Git sees normal LFS pointers in the repo; the actual binaries live on a Nextcloud instance.

## How it works

1. `.gitattributes` marks `*.dta` and `*.rds` files for LFS tracking.
2. `.lfsconfig` documents the custom transfer agent settings, but **git-lfs 3.x ignores them there** (security restriction on executable-code keys). The settings must live in `.git/config` — see Setup requirements below.
3. When `git push`/`git pull` runs, Git LFS spawns `lfs-nextcloud-agent.py` as a subprocess and communicates via **JSON messages over stdin/stdout** (the LFS custom transfer protocol).
4. The agent uploads/downloads files to Nextcloud via WebDAV, mirroring Git LFS's internal directory layout: `<LFS_PATH>/<oid[:2]>/<oid[2:4]>/<oid>`.

## Setup requirements

- Python ≥ 3.10 + Poetry; R ≥ 4.1 + renv
- `brew install git-lfs` (or distro equivalent) — must be installed before any commit/push that involves LFS files, otherwise git treats them as regular binaries
- `.env` file (git-ignored) with:
  ```
  NEXTCLOUD_URL=https://your-nextcloud.com
  NEXTCLOUD_USER=your_username
  NEXTCLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
  NEXTCLOUD_LFS_PATH=LFS/malaria-sim
  ```
- Custom transfer agent registered in `.git/config` (once per clone, not propagated by git):
  ```bash
  git config lfs.standalonetransferagent nextcloud-agent
  git config lfs.customtransfer.nextcloud-agent.path "$(poetry env info --path)/bin/python3"
  git config lfs.customtransfer.nextcloud-agent.args lfs-nextcloud-agent.py
  ```
  The `path` must point to the **poetry venv python** (not bare `python3`) so the `requests` dependency is on the path. git-lfs spawns the agent outside any active shell environment.

## Running / testing the agent

```bash
# Install dependencies
poetry install
Rscript -e "renv::restore()"

# Run the example simulation (generates ~30 MB .dta in outputs/simulations/)
Rscript code/simulate.R [seed] [n_individuals] [timesteps]

# Verify LFS is tracking files
git lfs ls-files

# Confirm a file landed on Nextcloud after push
curl -u $NEXTCLOUD_USER:$NEXTCLOUD_APP_PASSWORD \
  $NEXTCLOUD_URL/remote.php/dav/files/$NEXTCLOUD_USER/$NEXTCLOUD_LFS_PATH/ \
  -X PROPFIND | grep -o '<d:href>[^<]*</d:href>'
```

Agent debug output goes to **stderr** (prefixed `[nextcloud-agent]`); stdout is reserved for the LFS protocol.

## Key file

`lfs-nextcloud-agent.py` — the entire transfer agent in one file. It handles the three-phase LFS protocol: handshake (`init` → `capability`), then `upload`/`download` events, then `terminate`.
