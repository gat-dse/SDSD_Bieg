# file contains code for generating an example "2D RC slab and post-tensioned concrete slab"

# IMPORT
import struct_analysis  # file with code for structural analysis
import plot_datasets_2D  # file with code for plotting results in a standardized way
import matplotlib.pyplot as plt
from pathlib import Path

import time
print("START slab_2D_rc_pt(Test260514).py", flush=True)
t0 = time.time()


# define system lengths for plot (datapoints on x-axis of plot)
lengths = [6, 8, 12]

# index of verified length (member values of that length will be printed)
idx_vrc = 1

# max. number of iterations per optimization. Higher value leads to better results,
# but post-tensioned slabs are much slower because each trial updates the PT design.
max_iter = 100

# define content of plot
criteria = ["ULS"]
optima = ["GWP"]

# define database
database_name = "database_260126.db"


# ----------------------------------------------------------------------------------------------------------------------
# create floor structure for concrete rectangular cross-section
bodenaufbau_rcdecke = [
    ["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
    ["'Unterlagsboden Zement, 85 mm'", False, False],
    ["'Glaswolle'", 0.03, False],
]
bodenaufbau_rc = struct_analysis.FloorStruc(bodenaufbau_rcdecke, database_name)
# ----------------------------------------------------------------------------------------------------------------------

# define loads on member
g2k = 0.75e3  # n.t. Einbauten
qk = 2e3  # Nutzlast

# define service limit state criteria
req = struct_analysis.Requirements()


def max_of_arrays(existing_data, new_data):
    return [max(a, b) for a, b in zip(existing_data, new_data)]


data_max = [0, 0, 0, 0]
vrfctn_members = []

# ----------------------------------------------------------------------------------------------------------------------
# CREATE AND PLOT DATASET FOR REINFORCED CONCRETE SLAB
mat_names_rc = ["'ready_mixed_concrete'"]
data_max_new, vrfctn_members_new = plot_datasets_2D.plot_dataset(
    lengths,
    database_name,
    criteria,
    optima,
    bodenaufbau_rc,
    req,
    "rc_rec",
    mat_names_rc,
    g2k,
    qk,
    max_iter,
    idx_vrc,
)
data_max = max_of_arrays(data_max, data_max_new)
vrfctn_members.append(vrfctn_members_new)

print(f"Done rc_rec after {time.time()-t0:.1f}s", flush=True)


# ----------------------------------------------------------------------------------------------------------------------
# CREATE AND PLOT DATASET FOR POST-TENSIONED CONCRETE SLAB
mat_names_pt = ["'ready_mixed_concrete'"]
data_max_new, vrfctn_members_new = plot_datasets_2D.plot_dataset(
    lengths,
    database_name,
    criteria,
    optima,
    bodenaufbau_rc,
    req,
    "pc_rec",
    mat_names_pt,
    g2k,
    qk,
    max_iter,
    idx_vrc,
)
data_max = max_of_arrays(data_max, data_max_new)
vrfctn_members.append(vrfctn_members_new)

print(f"Done rc_rec after {time.time()-t0:.1f}s", flush=True)



# DEFINE LABELS OF PLOTS
plotted_data = [
    ["h$_{struct}$", "[m]"],
    ["h$_{tot}$", "[m]"],
    ["GWP$_{struct}$", "[kg-CO$_2$-eq]"],
    ["GWP$_{tot}$", "[kg-CO$_2$-eq]"],
]

# ADD LABELS, LEGEND, AXIS LIMITS AND GRID TO THE PLOTS
for idx, info in enumerate(plotted_data):
    plt.subplot(2, 2, idx + 1)
    plt.xlabel("l [m]", fontsize=12)
    plt.ylabel(info[0] + " " + info[1], fontsize=12)
    if idx % 2 == 0:
        plt.axis((min(lengths), max(lengths), 0, max(data_max[idx], data_max[idx + 1])))
    else:
        plt.axis((min(lengths), max(lengths), 0, max(data_max[idx], data_max[idx - 1])))
    plt.grid()


# PRINT VERIFICATION MEMBERS
for mem_group in vrfctn_members:
    for i, mem in enumerate(mem_group[0]):
        mem.calc_qk_zul_gzt()
        mem.get_fire_resistance()
        print()
        print(f"Verification member #{mem_group[1][i]}")
        print("section type =", mem.section.section_type)
        print("h =", round(mem.section.h, 3), "[m]")
        print("GWP =", round(mem.section.co2, 2), "[kg CO2-eq/m2]")
        print("qk_zul_gzt =", round(mem.qk_zul_gzt, 2), "[N/m2]")
        print("w_install/use/app =", round(mem.w_install, 5), round(mem.w_use, 5), round(mem.w_app, 5), "[m]")
        print("f1 =", round(mem.f1, 2), "[Hz]")
        if mem.section.section_type == "pc_rec":
            print("Psx/Psy =", round(mem.section.Psx / 1e3, 2), round(mem.section.Psy / 1e3, 2), "[kN]")
            print("sin(beta_x/y) =", tuple(round(v, 4) for v in mem.section.calc_prestress_sin_beta()))

# SAVE FIGURE TO FILE
output_dir = Path("plots")
output_dir.mkdir(exist_ok=True)
output_path = output_dir / "rc_vs_pc_comparison.png"
plt.savefig(output_path, dpi=600, bbox_inches='tight')  # Increased DPI for better quality

# SHOW FIGURE
#plt.show()
