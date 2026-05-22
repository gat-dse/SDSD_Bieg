#!/bin/bash
#SBATCH --job-name=final_comparison
#SBATCH --time=24:00:00
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"
mkdir -p euler_outputs plots
python "$SCRIPT_DIR/run_final_comparison.py"
python "$SCRIPT_DIR/plot_final_comparison_cross_sections.py"
