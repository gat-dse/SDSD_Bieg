# Test File to validate TCC slab


# IMPORT
import struct_analysis  # file with code for structural analysis
import struct_optimization
import struct_optimization  # file with code for structural optimization
#import matplotlib.pyplot as plt

# INPUT
database_name = "database_260126.db"  # define database name

# create material for reinforced concrete cross-section, derive corresponding design values
concrete1 = struct_analysis.ReadyMixedConcrete("'C30/37'", database_name)  # create a concrete material object
concrete1.get_design_values()
rebar1 = struct_analysis.SteelReinforcingBar("'B500B'", database_name)  # create a rebar material object
rebar1.get_design_values()
timber1 = struct_analysis.Wood("'GL24h'", database_name)  # create a Wood material object
timber1.get_design_values()
connector1 = struct_analysis.ConnectorTCC("'DBS_10'", database_name)  # create a connector material object

# create TCC ribbed cross-section
section = struct_analysis.TCC(concrete1, rebar1, timber1, connector1, 0.25, 0.6, 0.08, 0.36, 0.12, 0.02, 6)

# create floor structure for tcc cross-section
bodenaufbau = [] #void for validation
bodenaufbau_tcc= struct_analysis.FloorStruc(bodenaufbau, database_name)

requirements = struct_analysis.Requirements()

# define loads on member
g2k = 0.75e3  # n.t. Einbauten
qk = 2e3  # Nutzlast (Kat A)

# define service limit state criteria
requirements = struct_analysis.Requirements()

system = struct_analysis.BeamSimpleSup(6)


# Create TCC member
member = struct_analysis.Member1D(section, system, bodenaufbau_tcc, requirements, g2k, qk)
opt_section = struct_optimization.get_optimized_section(member, "ENV", "GWP", 150)

print("opt section h_w= ", opt_section.h_w)
print("opt section h_c= ", opt_section.h_c)
print("s= ", opt_section.s)
print("a_ribs= ", opt_section.a_ribs)
print("b_w= ", opt_section.b_w)
print("d =", opt_section.d)
print("b_ceff= ", opt_section.b_ceff)


print("Mu_0= ", round(opt_section.Mu[0],2))
print("Mu_inf= ", round(opt_section.Mu[1],2))
print("Vu_0= ", round(opt_section.Vu[0],2))
print("Vu_inf= ", round(opt_section.Vu[1],2))

print("psi_ULS",opt_section.psi_ULS)
print("psi_SLS",opt_section.psi_SLS)

print("gamma_ULS_0", opt_section.gamma_ULS[0])
print("gamma_ULS_inf", opt_section.gamma_ULS[1])
print("gamma_SLS_0", opt_section.gamma_SLS[0])
print("gamma_SLS_inf", opt_section.gamma_SLS[1])

print("a_ULS", opt_section.a_ULS)
print("a_SLS", opt_section.a_SLS)

print("EI_ULS_0= ", round(opt_section.EI_ULS[0],2))
print("EI_ULS_inf= ", round(opt_section.EI_ULS[1],2))
print("EI_SLS_0= ", round(opt_section.EI_SLS[0],2))
print("EI_SLS_inf= ", round(opt_section.EI_SLS[1],2))


member.calc_qk_zul_gzt()
print("qk_zul_gzt =", member.qk_zul_gzt)
print("Feuerwiderstand:")
member.get_fire_resistance()
print(member.fire_resistance)


print("w_inst_adm=", round(member.w_install_adm,5))
print("w_use_adm=", round(member.w_use_adm,5))
print("w_app_adm=", round(member.w_app_adm,5))