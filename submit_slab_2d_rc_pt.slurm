#!/bin/bash
#SBATCH --job-name=slab_2d_rc_pt
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4G
#SBATCH --array=0-4%5
#SBATCH --output=euler_outputs/slab_2d_rc_pt-%A_%a.out
#SBATCH --error=euler_outputs/slab_2d_rc_pt-%A_%a.err

set -euo pipefail

module purge
source ~/miniconda3/etc/profile.d/conda.sh
conda activate sdsd

export MPLBACKEND=Agg
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

cd "$SLURM_SUBMIT_DIR"
mkdir -p euler_outputs plots

CRITERIA=(ENV ULS SLS1 SLS2 FIRE)
export SDSD_CRITERION="${CRITERIA[$SLURM_ARRAY_TASK_ID]}"

python "slab_2D_rc_pt(Test260514).py"
