#!/bin/bash
#SBATCH --job-name=final_comparison
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4G
#SBATCH --output=euler_outputs/final_comparison-%j.out
#SBATCH --error=euler_outputs/final_comparison-%j.err

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
python run_final_comparison.py
