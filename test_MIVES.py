# Test file for MIVES

# IMPORT
import struct_analysis  # file with code for structural analysis
import struct_optimization
from prettytable import PrettyTable
import struct_optimization  # file with code for structural optimization
import MIVES  # file with code for MIVES evaluation of members
#import matplotlib.pyplot as plt

# INPUT
database_name = "database_260126.db"  # define database name


# define loads on member
g2k = 0.75e3  # n.t. Einbauten
qk = 2e3  # Nutzlast (Kat A)
requirements = struct_analysis.Requirements()

# create material for tcc
concrete1 = struct_analysis.ReadyMixedConcrete("'C30/37'", database_name)  # create a concrete material object
concrete1.get_design_values()
rebar1 = struct_analysis.SteelReinforcingBar("'B500B'", database_name)  # create a rebar material object
rebar1.get_design_values()
timber1 = struct_analysis.Wood("'GL24h'", database_name)  # create a Wood material object
timber1.get_design_values()
connector1 = struct_analysis.ConnectorTCC("'DBS_10'", database_name)  # create a connector material object

# create TCC ribbed cross-section
section_tcc = struct_analysis.TCC(concrete1, rebar1, timber1, connector1, 0.25, 0.6, 0.08, 0.36, 0.12, 0.02, 6)

# create floor structure for tcc cross-section
bodenaufbau_tcc = [["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
                       ["'Unterlagsboden Zement, 85 mm'", False, False],
                       ["'Glaswolle'", 0.03, False]]
bodenaufbau_tcc= struct_analysis.FloorStruc(bodenaufbau_tcc, database_name)

# define system
system_tcc = struct_analysis.BeamSimpleSup(6)

# Create TCC member
member_tcc = struct_analysis.Member1D(section_tcc, system_tcc, bodenaufbau_tcc, requirements, g2k, qk)
opt_section_tcc = struct_optimization.get_optimized_section(member_tcc, "ENV", "GWP", 150)
opt_member_tcc = struct_analysis.Member1D(opt_section_tcc, system_tcc, bodenaufbau_tcc, requirements, g2k, qk)

# create material for solid wooden cross-section, derive corresponding design values
timber2 = struct_analysis.Wood("'GL24h'", database_name)  # create a Wood material object
timber2.get_design_values()

# create solid wooden cross-section
section_solid = struct_analysis.RectangularWood(timber2, 1, 0.2)

# create floor structure for solid wooden cross-section
bodenaufbau_solid = [["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
                     ["'Unterlagsboden Zement, 85 mm'", False, False], ["'Glaswolle'", 0.03, False],
                     ["'Kies gebrochen'", 0.12, False]]
bodenaufbau_solid = struct_analysis.FloorStruc(bodenaufbau_solid, database_name)

# define system
system_solid = struct_analysis.BeamSimpleSup(6)

# Create solid wooden member
member_solid = struct_analysis.Member1D(section_solid, system_solid, bodenaufbau_solid, requirements, g2k, qk)
opt_section_solid = struct_optimization.get_optimized_section(member_solid, "ENV", "GWP", 150)
opt_member_solid = struct_analysis.Member1D(opt_section_solid, system_solid, bodenaufbau_solid, requirements, g2k, qk)

# create material for concrete rectangular cross-section, derive corresponding design values
concrete2 = struct_analysis.ReadyMixedConcrete("'C30/37'", database_name)  # create a concrete material object
concrete2.get_design_values()
rebar2 = struct_analysis.SteelReinforcingBar("'B500B'", database_name)  # create a rebar material object
rebar2.get_design_values()

# create concrete rectangular cross-section
section_rc = struct_analysis.RectangularConcrete(concrete2, rebar2, 1, 0.2, 0.01, 0.15, 0.01, 0.15)

# create floor structure for concrete rectangular cross-section
bodenaufbau_rc = [["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
                       ["'Unterlagsboden Zement, 85 mm'", False, False],
                       ["'Glaswolle'", 0.03, False]]
bodenaufbau_rc = struct_analysis.FloorStruc(bodenaufbau_rc, database_name)

# define system
system_rc = struct_analysis.BeamContinuousSupPl(6)

# Create concrete rectangular member
member_rc = struct_analysis.Member1D(section_rc, system_rc, bodenaufbau_rc, requirements, g2k, qk)
opt_section_rc = struct_optimization.get_optimized_section(member_rc, "ENV", "GWP", 150)
opt_member_rc = struct_analysis.Member1D(opt_section_rc, system_rc, bodenaufbau_rc, requirements, g2k, qk)

# MIVES evaluation
members = [opt_member_tcc, opt_member_solid, opt_member_rc]
mives_evaluator = MIVES.MIVESEvaluator(members)

# Create a table for results
table = PrettyTable()
table.field_names = ["Property", "TCC", "Solid Wood", "Concrete Rectangular"]  # Add column for concrete rectangular member

# Map display names to actual keys in the member_data dictionary
key_mapping = {
    "Cost (CHF/m2)": "cost",
    "Construction Time (mh/m2)": "construction_time",
    "CO2 Emissions (kg CO2/m2)": "co2",
    "Weight (N/m2)": "weight",
    "Total Height (h_tot, m)": "h_tot",
    "Installation Height (h_installation, m)": "h_installation"
}

# Add rows to the table dynamically based on the number of sections
for name, key in key_mapping.items():
    row = [name]
    for member_data in mives_evaluator.members_data:
        row.append(member_data[key])
    table.add_row(row)

# Print the table
print(table)

# Print MIVES scores
scores = mives_evaluator.evaluate()  # Get scores for all members
for idx, (S, v_eco, v_cost, v_social) in enumerate(scores):
    print(f"{table.field_names[idx+1]} MIVES scores:")
    print(f"  Total Sustainability Index: {S:.2f}")
    print(f"  Ecology Score: {v_eco:.2f}")
    print(f"  Economy Score: {v_cost:.2f}")
    print(f"  Social Score: {v_social:.2f}")
    print("-" * 40)

#plot 
#mives_evaluator.plot_mives_scores(scores)