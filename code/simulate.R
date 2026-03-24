## Malaria transmission simulation
## Generates a large individual-level output dataset saved as .dta
##
## Usage:
##   Rscript code/simulate.R [seed] [n_individuals] [timesteps]
##
## Defaults: seed=42, n=50000, timesteps=365

library(haven)
library(dplyr)

# ── Parameters ────────────────────────────────────────────────────────────────

args <- commandArgs(trailingOnly = TRUE)
parse_arg <- function(x, default) { v <- suppressWarnings(as.integer(x)); if (!is.na(v)) v else default }

seed      <- parse_arg(args[1], 42L)
n_ind     <- parse_arg(args[2], 50000L)
timesteps <- parse_arg(args[3], 365L)

set.seed(seed)
cat(sprintf("Simulation: seed=%d  n=%d  timesteps=%d\n", seed, n_ind, timesteps))

# ── Model parameters ──────────────────────────────────────────────────────────

pfpr          <- 0.30   # baseline PfPR2-10
bite_rate     <- 0.25   # daily probability of infectious bite
recovery_rate <- 1 / 14 # daily recovery probability (~14-day infectious period)
reinfection   <- 0.05   # additional daily risk while recovered

# ── Initialise population ─────────────────────────────────────────────────────

pop <- tibble(
  id          = seq_len(n_ind),
  age         = sample(0:80, n_ind, replace = TRUE),
  sex         = sample(c("M", "F"), n_ind, replace = TRUE),
  # ITN use: higher in children <5
  itn         = rbinom(n_ind, 1, ifelse(age < 5, 0.70, 0.45)),
  # Initial infection status drawn from baseline PfPR
  infected    = rbinom(n_ind, 1, pfpr),
  # Days since last infection (0 if currently infected)
  days_inf    = ifelse(infected == 1, sample(0:13, n_ind, replace = TRUE), 0L),
  # Cumulative infections over simulation
  n_infections = infected
)

# ── Run time-loop and record monthly snapshots ────────────────────────────────

snapshots <- vector("list", timesteps %/% 30)
snap_idx  <- 1L

for (t in seq_len(timesteps)) {

  # Effective bite rate reduced by ~50% for ITN users
  eff_bite <- bite_rate * ifelse(pop$itn == 1, 0.50, 1.0)

  # Recovery
  recovers        <- pop$infected == 1 & runif(n_ind) < recovery_rate
  pop$infected[recovers]  <- 0L
  pop$days_inf[recovers]  <- 0L

  # New infections (susceptibles only)
  susceptible     <- pop$infected == 0
  new_inf         <- susceptible & runif(n_ind) < (eff_bite + reinfection * !susceptible)
  pop$infected[new_inf]   <- 1L
  pop$days_inf[new_inf]   <- 0L
  pop$n_infections        <- pop$n_infections + as.integer(new_inf)

  # Advance days infectious
  pop$days_inf[pop$infected == 1] <- pop$days_inf[pop$infected == 1] + 1L

  # Monthly snapshot
  if (t %% 30 == 0) {
    snapshots[[snap_idx]] <- pop |>
      mutate(day = t, month = t %/% 30)
    snap_idx <- snap_idx + 1L
  }
}

# ── Combine and save ──────────────────────────────────────────────────────────

results <- bind_rows(snapshots) |>
  mutate(
    seed      = seed,
    n_ind     = n_ind,
    timesteps = timesteps
  )

out_dir  <- file.path("outputs", "simulations")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
out_file <- file.path(out_dir,
  sprintf("sim_%s_seed%d_n%d_t%d.dta",
          format(Sys.Date(), "%Y%m%d"), seed, n_ind, timesteps))

write_dta(results, out_file)

cat(sprintf("Saved %d rows x %d cols → %s (%.1f MB)\n",
            nrow(results), ncol(results), out_file,
            file.size(out_file) / 1e6))
