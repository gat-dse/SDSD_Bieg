#!/bin/bash
#SBATCH --job-name=final_comparison
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=4G
#SBATCH --output=/cluster/home/jobieg/SDSD_Bieg/euler_outputs/final_comparison-%j.out
#SBATCH --error=/cluster/home/jobieg/SDSD_Bieg/euler_outputs/final_comparison-%j.err

set -euo pipefail

module purge
source /cluster/home/jobieg/miniconda3/etc/profile.d/conda.sh
conda activate sdsd

export MPLBACKEND=Agg
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
unset SDSD_SCENARIOS
unset SDSD_SYSTEMS
unset SDSD_LENGTHS
export SDSD_MAX_ITER=150

REPO_ROOT="/cluster/home/jobieg/SDSD_Bieg"
SCRIPT_DIR="$REPO_ROOT/FinalComparison"

cd "$REPO_ROOT"
echo "PWD: $(pwd)"
echo "USER: $(whoami)"
echo "REPO_ROOT: $REPO_ROOT"
echo "SCRIPT_DIR: $SCRIPT_DIR"

mkdir -p "$REPO_ROOT/euler_outputs" "$REPO_ROOT/plots" "$REPO_ROOT/outputs/matplotlib"
python "$SCRIPT_DIR/run_final_comparison.py"
python "$SCRIPT_DIR/plot_final_comparison_cross_sections.py"
python "$SCRIPT_DIR/analyze_final_comparison.py"
