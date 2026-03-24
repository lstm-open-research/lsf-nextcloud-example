How it fits together
Your Machine                GitHub              Nextcloud
─────────────               ──────              ─────────
git push ──► .dta pointer ──► repo         .dta file ──► /lfs-objects/
             (tiny text)      (code)         (actual binary, via WebDAV)

Nextcloud Setup
First, create a dedicated folder in Nextcloud for LFS objects and create an App Password (never use your main password in scripts):
Nextcloud → Settings → Security → Devices & Sessions → Create new app password
Your WebDAV base URL will be:
https://your-nextcloud.com/remote.php/dav/files/YOUR_USERNAME/

Project Structure
project/
├── .gitattributes
├── .lfsconfig
├── lfs-nextcloud-agent.py
├── .env                    # credentials (git-ignored!)
├── code/
└── outputs/
    └── simulations/


Collaborator Setup
Anyone cloning your repo needs to:
```
bash# 
Clone repo (gets code + LFS pointers)
git clone https://github.com/you/malaria-sim.git
cd malaria-sim
```

# Add their own .env with Nextcloud credentials
```cp .env.example .env```   # you should commit a template .env.example
```nano .env```              # fill in their credentials

# Pull actual .dta files from Nextcloud
```
git lfs pull
```
Provide a .env.example in the repo with empty values as a template:
bash# .env.example  ← commit this one
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_USER=
NEXTCLOUD_APP_PASSWORD=
NEXTCLOUD_LFS_PATH=LFS/malaria-sim

Daily Workflow (unchanged from normal git)
bash# In R: run simulation, save output
# write_dta(output, "outputs/simulations/sim_20250217_seed42.dta")

git add outputs/simulations/sim_20250217_seed42.dta
git commit -m "sim: seed=42, pop=10000, timesteps=365, pfpr=0.3"
git push   # pointer goes to GitHub, .dta goes to Nextcloud via WebDAV

Verifying it works
bash# Check what LFS is tracking
git lfs ls-files

# Confirm the file landed on Nextcloud
curl -u your_user:your_app_password \
  https://your-nextcloud.com/remote.php/dav/files/your_user/LFS/malaria-sim/ \
  -X PROPFIND | grep -o '<d:href>[^<]*</d:href>'