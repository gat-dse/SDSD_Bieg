# File enthält Code für die Strukturanalyse (Bauteil- und Querschnittsanalyse)
# units: [m], [kg], [s], [N], [CHF]

# Abgebildete Materialien:
# - Beton
# - Betonstahl
# - Holz
# - Verbindung für Holz-Beton-Verbund (Jonathan Bieg)
#
# Abgebildete Querschnitte 1D:
# - Betonrechteck-QS (Optimierung obere Bewehrungslage, Durchstanzen - Jonathan Bieg)
# - Holzrechteck-QS
# - Beton-Rippen-QS
# - Holz-Hohlkasten-QS
# - Holz-Beton-Verbund-QS (Jonathan Bieg)
# - Betonrechteck-QS vorgespannt (Jonathan Bieg)
#
# Abgebildete Statische Systeme 1D:
# - Einfacher Balken
# - Durchlaufträger
#
#Statische Systeme 2D: Rechteckiger Grundriss
# - Linienlager 4-seitig gelagert (eingespannt oder gelenkig) (Jonathan Bieg)
# - Punktlager 4-seitig gelagert (eingespannt) (Jonathan Bieg)
#
# Weitere Klassen:
# - Bauteil 1D
# - Bauteil 2D (Jonathan Bieg)
# - Bodenaufbauschicht
# - Automatische generierung Bodenaufbau (Jonathan Bieg)
# - Rechteckquerschnitte
# - Anforderungen 

import copy
import math
import sqlite3  # import modul for SQLite
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, root_scalar
from scipy.optimize import least_squares


def concrete_member_is_uncracked(member):
    """Return whether all available concrete design moments stay below cracking."""
    section = member.section
    moment_pairs = [(member.mkd_p, member.mkd_n)]
    if hasattr(member, "mkd_p_y") and hasattr(member, "mkd_n_y"):
        moment_pairs.append((member.mkd_p_y, member.mkd_n_y))
    return all(
        positive_moment < section.mr_p and negative_moment > section.mr_n
        for positive_moment, negative_moment in moment_pairs
    )


#CONSTANTS--------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------
g = 10.0 #simplified gravitational acceleration [m/s^2]


#DEFINITONS OF MATERIAL PROPERTIES--------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------
class Wood:
    # defines properties of wooden material
    def __init__(self, mech_prop, database, prod_id="undef"):  # retrieve basic mechanical data from database
        self.mech_prop = mech_prop
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        # get mechanical properties from database
        inquiry = ("SELECT strength_bend, strength_shea, E_modulus, density_load, burn_rate, phi FROM material_prop WHERE name = " + mech_prop)
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.fmk, self.fvd, self.Emmean, self.weight, self.burn_rate, self.phi = result[0]
        # get GWP properties from database
        if prod_id == "undef":  # no specific product is defined, chose first product entry with required mechanical
            # properties in database
            inquiry = "SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products LIMIT 1"
        else:
            inquiry = "SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE PRO_ID=" + prod_id
        cursor.execute(inquiry)
        result = cursor.fetchall()
        # self.prod_id, self.density, self.GWP, self.cost, self.cost2 = result[0]
        self.prod_id, density, GWP, cost, construction_time = result[0]
        self.GWP = GWP/1e3  # transform unit from [kg-Co2-eq/t] to [kg-Co2-eq/kg]
        self.density = float(density)
        self.specific_weight = self.density * g
        self.cost = cost #CHF/m3
        self.construction_time = construction_time #h/m3
        self.cost2 = 0 
        self.fmd = self.get_design_values()

    def get_design_values(self, gamma_m=1.7, eta_m=1, eta_t=1, eta_w=1):  # calculate design values
        if self.mech_prop[1:3] == "GL":
            gamma_m = 1.5  # SIA 265, 2.2.5: reduzierter Sicherheitsbeiwert für BSH
        fmd = self.fmk * eta_m * eta_t * eta_w / gamma_m  # SIA 265, 2.2.2, Formel (3)
        return fmd


class ReadyMixedConcrete:
    # defines properties of concrete material
    def __init__(self, mech_prop, database, dmax=32,
                 prod_id="undef"):  # retrieve basic mechanical data from database (self, table,
        self.mech_prop = mech_prop

        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        # get mechanical properties from database
        inquiry = ("SELECT strength_comp, strength_tens, E_modulus, density_load, phi FROM material_prop WHERE name="
                   + mech_prop)
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.fck, self.fctm, self.Ecm, self.weight, self.phi = result[0]
        # get GWP properties from database
        if prod_id == "undef":  # no specific product is defined, chose first product entry with required mechanical
            # properties in database
            # inquiry = ("""
            #         SELECT PRO_ID, density, Total_GWP, cost, cost2 FROM products WHERE "material [string]" LIKE """ + mech_prop
            #            )
            inquiry = ("""SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE MECH_PROP LIKE """
                       + mech_prop)
        else:
            # inquiry = ("""SELECT PRO_ID, density, Total_GWP, cost, cost2 FROM products WHERE PRO_ID LIKE """ + prod_id
            #            )
            inquiry = ("""SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE PRO_ID LIKE """
                       + prod_id)
        cursor.execute(inquiry)
        result = cursor.fetchall()
        # self.prod_id, self.density, self.GWP, self.cost, self.cost2 = result[0]
        self.prod_id, density, GWP, cost, construction_time = result[0]
        self.GWP = GWP/1e3  # transform unit from [kg-Co2-eq/t] to [kg-Co2-eq/kg]
        self.density = float(density)
        self.specific_weight = self.density * g
        self.cost = cost #CHF/m3
        self.cost2 = 75 #CHF/m2 additional cost for formwork (flat slabs)
        self.construction_time = construction_time #h/m3
        self.construction_time_scaffold = 0.7 #h/m2 additional construction time for scaffolding
        self.dmax = dmax
        self.fcd, self.tcd, self.ec2d = self.get_design_values()

    def get_design_values(self, gamma_c=1.5, eta_t=1):  # calculate design values
        eta_fc = min((30e6 / self.fck) ** (1 / 3), 1)  # SIA 262, 4.2.1.2, Formel (26)
        fcd = self.fck * eta_fc * eta_t / gamma_c  # SIA 262, 2.3.2.3, Formel (2)
        tcd = 0.3 * eta_t * 1e6 * (self.fck * 1e-6) ** 0.5 / gamma_c  # SIA 262, 2.3.2.4, Formel (3)
        ec2d = 0.003  # SIA 262, 4.2.4, Tabelle 8
        return fcd, tcd, ec2d

class SteelReinforcingBar:
    # defines properties of reinforcement  material
    def __init__(self, mech_prop, database, prod_id="undef"):
        # retrieve basic mechanical data from database (self, table, database name)
        self.mech_prop = mech_prop
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        # get mechanical properties from database
        inquiry = "SELECT strength_tens, E_modulus FROM material_prop WHERE name=" + mech_prop
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.fsk, self.Es = result[0]
        # get GWP properties from database
        if prod_id == "undef":  # no specific product is defined, chose first product entry with required mechanical
            # properties in database
            inquiry = "SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE MECH_PROP=" + mech_prop
        else:
            inquiry = "SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE PRO_ID=" + prod_id
        cursor.execute(inquiry)
        result = cursor.fetchall()
        #self.prod_id, density, self.GWP, self.cost = result[0]
        self.prod_id, density, GWP, cost, construction_time = result[0]
        self.GWP = GWP/1e3  # transform unit from [kg-Co2-eq/t] to [kg-Co2-eq/kg]
        self.density = float(density)
        self.specific_weight = self.density * g
        self.cost = cost #CHF/m3
        self.construction_time = construction_time #h/m3
        self.fsd = self.get_design_values()

    def get_design_values(self, gamma_s=1.15):  # calculate design values
        fsd = self.fsk / gamma_s  # SIA 262, 2.3.2.5, Formel (4)
        return fsd
    
class PrestressingSteel:
    #defines properties of prestressing steel material
    def __init__(self, mech_prop, database, prod_id="undef"):
        # retrieve basic mechanical data from database (self, table, database name)
        self.mech_prop = mech_prop
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        # get mechanical properties from database
        inquiry = "SELECT strength_tens, E_modulus FROM material_prop WHERE name=" + mech_prop
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.fpk, self.Ep = result[0]
        # get GWP properties from database
        if prod_id == "undef":
            inquiry = "SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE MECH_PROP=" + mech_prop
        else:
            inquiry = "SELECT PRO_ID, DENSITY, Total_GWP, Cost, T_construction FROM products WHERE PRO_ID=" + prod_id
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.prod_id, density, GWP, cost, construction_time = result[0]
        self.GWP = GWP/1e3  # transform unit from [kg-Co2-eq/t] to [kg-Co2-eq/kg]
        self.density = 7850.0 if density is None else float(density)
        self.specific_weight = self.density * g
        self.cost = cost    #CHF/m3
        self.construction_time = construction_time #h/m3
        self.fp01k, self.fpd = self.get_design_values()

    def get_design_values(self, gamma_p=1.15):  # calculate design values
        fp01k = self.fpk * 0.86 #simplified assumption, not the standard value, but fine
        fpd = fp01k / gamma_p
        return fp01k, fpd


class ConnectorTCC:
    # defines properties of connectors for timber-concrete composite slabs
    def __init__(self, mech_prop, database):
        # retrieve basic mechanical data from database (self, table, database name)
        self.mech_prop = mech_prop
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        # get mechanical properties from database
        inquiry = "SELECT K_ser, Cost, T_construction FROM connector_TCC WHERE name=" + mech_prop
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.K_ser, self.cost, self.construction_time = result[0]
        # Now also extract connector name
        inquiry = "SELECT name FROM connector_TCC WHERE name=" + mech_prop
        cursor.execute(inquiry)
        result = cursor.fetchall()
        self.name = result[0][0]
        try:
            inquiry = "SELECT GWP FROM connector_TCC WHERE name=" + mech_prop
            cursor.execute(inquiry)
            result = cursor.fetchall()
            self.GWP = 0.0 if result[0][0] is None else float(result[0][0])
        except sqlite3.OperationalError:
            self.GWP = 0.0

    def get_design_values(self):
        return self.K_ser 


#-----------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------
class Section:
    # contains fundamental section properties like section type weight, resistance and stiffness
    def __init__(self, section_type):
        self.section_type = section_type
        # The following properties are defined in the specific cross-section classes. However, it could make sense to
        # provide them in this more general parent class.
        #
        # properties:
        # self.mu_max = float
        # self.mu_min = float
        # self.vu = float
        # self.qs_class_n = int
        # self.qs_class_p = int
        # self.g0k = float
        # self.ei1 = float
        # self.co2 = float
        # self.cost = float


class SupStrucRectangular(Section):
    # defines cross-section dimensions and has methods to calculate static properties of rectangular,
    # non-cracked sections
    def __init__(self, section_type, b, h, phi=0):  # create a rectangular object
        super().__init__(section_type)
        self.b = b  # width [m]
        self.h = h  # height [m]
        self.a_brutt = self.calc_area()
        self.iy = self.calc_moment_of_inertia()
        self.phi = phi

    def calc_area(self):
        #  in: width b [m], height h [m]
        #  out: area [m^2]
        a_brutt = self.b * self.h
        return a_brutt

    def calc_moment_of_inertia(self):
        #  in: width b [m], height h [m]
        #  out: second moment of inertia Iy [m^4]
        iy = self.b * self.h ** 3 / 12
        return iy

    def calc_strength_elast(self, fy, ty):
        #  in: yielding strength fy [Pa], shear strength ty [Pa]
        #  out: elastic bending resistance mu_el [Nm], elastic shear resistance vu_el [N]
        mu_el = self.iy * fy * 2 / self.h
        vu_el = self.b * self.h * ty / 1.5
        return mu_el, vu_el

    def calc_strength_plast(self, fy, ty):
        #  in: yielding strength fy [Pa], shear strength ty [Pa]
        #  out: plastic bending resistance mu_pl [Nm], plastic shear resistance vu_pl [N]
        mu_pl = self.b * self.h ** 2 * fy / 4
        vu_pl = self.b * self.h * ty
        return mu_pl, vu_pl

    def calc_weight(self, material):
        #  out: product-specific weight of cross section per m length [N/m]
        w = material.specific_weight * self.a_brutt
        return w

#........................................................................
class RectangularWood(SupStrucRectangular, Section):
    # defines properties of rectangular, wooden cross-section
    def __init__(self, wood_type, b, h, phi=0.6, xi=0.02, ei_b=0.0):  # create a rectangular timber object
        section_type = "wd_rec"
        super().__init__(section_type, b, h, phi)
        self.wood_type = wood_type
        mu_el, vu_el = self.calc_strength_elast(wood_type.fmd, wood_type.fvd)
        self.mu_max, self.mu_min = [mu_el, -mu_el]  #Readme: Why is this needed for wood? -> is not needed for wood.
        # However, as the same resistance values should be provided for all cross-sections, I defined them for both
        # directions for wood too
        self.vu_p, self.vu_n = vu_el, vu_el
        self.qs_class_n, self.qs_class_p = [3, 3]  # Required cross-section class: 1:PP, 2:EP, 3:EE
        self.g0k = self.calc_weight(wood_type) # dead weight of cross section [N/m]
        self.ei1 = self.wood_type.Emmean * self.iy  # elastic stiffness [Nm^2]
        self.volume_wood = self.a_brutt / self.b
        self.co2_wood = self.volume_wood * self.wood_type.GWP * self.wood_type.density
        self.cost_wood = self.volume_wood * self.wood_type.cost
        self.co2 = self.a_brutt * self.wood_type.GWP * self.wood_type.density/self.b  # [kg_CO2_eq/m]
        self.cost = self.a_brutt * self.wood_type.cost/self.b # [CHF/m]
        self.construction_time = self.a_brutt * self.wood_type.construction_time/self.b # [h/m]
        self.ei_b = ei_b  # stiffness perpendicular to direction of span [Nm^2]
        self.xi = xi  # damping factor, preset value see: HBT, Page 47 (higher value for some buildups possible)
        self.h_installation = 0 # no room for installation of services
        self.w = self.g0k / self.b # weight of cross section per m2 [N/m2]

    @staticmethod
    def fire_resistance(member):
        bnds = [(0, 240)]   #Randbedingungen für Definition Brand - mind. 0 min max. 240 min
        t0 = 60     #Brandeinwirkungsdauer
        max_t = minimize(RectangularWood.fire_minimizer, t0, args=[member], bounds=bnds)    #Brandwiderstanddauer → maximale Brandeinwirkungszeit
        t_max = max_t.x[0]
        return t_max

    @staticmethod
    def fire_minimizer(t, args):
        member = args[0]
        rem_sec = RectangularWood.remaining_section(member.section, member.fire, t)
        mu_fire = 1.8 * rem_sec.mu_max
        vu_fire = 1.8 * rem_sec.vu_p  # SIA 265 (51)
        qd_fire = member.psi[2] * member.qk + member.gk
        qd_fire_zul = min(mu_fire / (max(member.system.alpha_m) * member.system.l_tot ** 2),
                          vu_fire / (max(member.system.alpha_v) * member.system.l_tot))
        to_opt = abs(qd_fire - qd_fire_zul)
        return to_opt

    @staticmethod
    def remaining_section(section, fire, t=60, dred=0.007):
        betan = section.wood_type.burn_rate
        dcharn = betan * t
        d_ef = dcharn + dred
        h_fire = max(section.h - d_ef * (fire[0] + fire[2]))
        b_fire = max(section.b - d_ef * (fire[1] + fire[3]), 0)
        rem_sec = RectangularWood(section.wood_type, b_fire, h_fire)
        return rem_sec

# ........................................................................
class RectangularConcrete(SupStrucRectangular):
    # defines properties of rectangular, reinforced concrete cross-section
    def __init__(self, concrete_type, rebar_type, b, h, di_xu, s_xu, di_xo, s_xo, di_yu=0.01, s_yu=0.15, di_yo=0.01, s_yo=0.15, di_bw=0.0, s_bw=0.15, n_bw=0,
                 phi=2.0, c_nom=0.02, xi=0.02, jnt_srch=0.15):
        # create a rectangular concrete object
        section_type = "rc_rec"
        super().__init__(section_type, b, h, phi)
        self.concrete_type = concrete_type
        self.rebar_type = rebar_type
        self.c_nom = c_nom #Bewehrungsüberdeckung
        self.bw = [[di_xu, s_xu], [di_xo, s_xo], [di_yu, s_yu],[di_yo, s_yo]] #Definition Biegebewehrung 4-Lagig. x-Richtung ist dabei die Haupttragrichtung, di = Durchmesser, s = Abstand, u = untere Lagen (positives Biegemoment), o = obere Lagen (negatives Biegemoment)
        self.bw_bg = [di_bw, s_bw, n_bw] #Definition Querkraftbewehrung
        mr = self.b * self.h ** 2 / 6 * 1.3 * self.concrete_type.fctm  #cracking moment
        self.mr_p, self.mr_n = mr, -mr #mr_p: positives Rissmoment, mr_n: negatives Rissmoment
        [self.d, self.ds] = self.calc_d() #Statische Höhe. d für positive Biegung (untere Lagen), ds für negative Biegung (obere Lagen)
        #TODO: x und y Richtung Berücksichtigen
        [self.mu_max, self.x_p, self.as_p, self.qs_class_p] = self.calc_mu('pos')
        [self.mu_min, self.x_n, self.as_n, self.qs_class_n] = self.calc_mu('neg')
        self.as_yu = np.pi * self.bw[2][0] ** 2 / (4 * self.bw[2][1]) * self.b
        self.as_yo = np.pi * self.bw[3][0] ** 2 / (4 * self.bw[3][1]) * self.b
        self.roh, self.rohs = self.as_p / self.d, self.as_n / self.ds
        [self.vu_p, self.vu_n, self.as_bw] = self.calc_shear_resistance()
        # Stagger shear reinforcement for material quantities: the calculated
        # resistance may be needed near supports, but the same amount is not
        # assumed over the full slab area.
        a_s_stat = self.as_p + self.as_n + self.as_yu + self.as_yo + 0.5 * self.as_bw
        self.joint_surcharge = jnt_srch  # surcharge for reinforcement joints, preset value is an assumption and has to be verified with literature
        a_s_tot = a_s_stat * (1 + self.joint_surcharge)  # rebar area without reinforcement joint surcharge
        self.g0k = self.calc_weight(self.a_brutt - a_s_tot, a_s_tot)
        co2_rebar = a_s_tot * self.rebar_type.GWP * self.rebar_type.density  # [kg_CO2_eq/m]
        co2_concrete = (self.a_brutt - a_s_tot) * self.concrete_type.GWP * self.concrete_type.density  # [kg_CO2_eq/m]
        self.volume_reinforcement = a_s_tot / self.b
        self.volume_concrete = (self.a_brutt - a_s_tot) / self.b
        self.volume_pt_steel = 0.0
        self.co2_rebar = co2_rebar / self.b
        self.co2_concrete = co2_concrete / self.b
        self.co2_pt_steel = 0.0
        self.cost_rebar = a_s_tot * self.rebar_type.cost / self.b
        self.cost_concrete = (self.a_brutt - a_s_tot) * self.concrete_type.cost / self.b + self.concrete_type.cost2
        self.cost_pt_steel = 0.0
        self.ei1 = self.concrete_type.Ecm * self.iy  # elastic stiffness concrete (uncracked behaviour) [Nm^2]
        self.co2 = (co2_rebar + co2_concrete)/self.b
        self.cost = (a_s_tot * self.rebar_type.cost + (self.a_brutt - a_s_tot) * self.concrete_type.cost)/self.b + self.concrete_type.cost2# [CHF/m]
        self.construction_time = (a_s_tot * self.rebar_type.construction_time + (self.a_brutt - a_s_tot) * self.concrete_type.construction_time)/self.b + self.concrete_type.construction_time_scaffold # [h/m]
        self.punching_steel_volume = 0.0
        self.punching_steel_co2 = 0.0
        self.punching_steel_cost = 0.0
        self.punching_steel_construction_time = 0.0
        self.ei_b = self.ei1
        self.xi = xi  # XXXXXXX preset value is an assumption. Has to be verified with literature. XXXXXXX
        self.ei2 = self.ei1 / self.f_w_ger(self.roh, self.rohs, 0, self.h, self.d)
        self.h_installation = self.h - 2*self.c_nom - self.bw[0][0] - self.bw[1][0] - self.bw[2][0] - self.bw[3][0]  # height available for installation of services
        self.w = self.g0k / self.b # weight of cross section per m2 [N/m2]

    def set_punching_reinforcement_volume(self, volume):
        """Include separately calculated punching steel in section impacts."""
        self.co2 -= self.punching_steel_co2
        self.cost -= self.punching_steel_cost
        self.construction_time -= self.punching_steel_construction_time

        self.punching_steel_volume = max(float(volume), 0.0)
        self.punching_steel_co2 = (
            self.punching_steel_volume * self.rebar_type.GWP * self.rebar_type.density
        )
        self.punching_steel_cost = self.punching_steel_volume * self.rebar_type.cost
        self.punching_steel_construction_time = (
            self.punching_steel_volume * self.rebar_type.construction_time
        )

        self.co2 += self.punching_steel_co2
        self.cost += self.punching_steel_cost
        self.construction_time += self.punching_steel_construction_time

    def calc_weight(self, concrete_area=None, reinforcement_area=0.0, pt_steel_area=0.0):
        #  out: product-specific weight of reinforced cross section per m length [N/m]
        concrete_area = self.a_brutt if concrete_area is None else max(concrete_area, 0.0)
        return (
            self.concrete_type.specific_weight * concrete_area
            + self.rebar_type.specific_weight * max(reinforcement_area, 0.0)
            + getattr(self, "pt_steel_type", self.rebar_type).specific_weight * max(pt_steel_area, 0.0)
        )

    def calc_d(self):
        # Simplification: Static height is height avg height between two layers of reinforcement
        d = self.h - self.c_nom - self.bw_bg[0] - self.bw[0][0] #Statische Höhe für Positives Biegemoment 
        ds = self.h - self.c_nom - self.bw_bg[0] - self.bw[1][0] #Statische Höhe für Negatives Biegemoment
        return d, ds

    def calc_mu(self, sign='pos'):
        #in: self
        #out: Biegewiderstand mu [Nm], Druckzonenhöhe x [m], Bewehrungsfläche a_s [m2], Querschnittsklasse qs_klasse []
        b = self.b  #Querschnittsbreite
        fsd = self.rebar_type.fsd
        fcd = self.concrete_type.fcd
        if sign == 'pos':
            [mu, x, a_s, qs_klasse] = self.mu_unsigned(self.bw[0][0], self.bw[0][1], self.d, b, fsd, fcd, self.mr_p)
        elif sign == 'neg':
            [mus, x, a_s, qs_klasse] = self.mu_unsigned(self.bw[1][0], self.bw[1][1], self.ds, b, fsd, fcd, self.mr_n)
            mu = -mus
        else:
            [mu, x, a_s, qs_klasse] = [0, 0, 0, 0]
            print("sign of moment resistance has to be 'neg' or 'pos'")
        return mu, x, a_s, qs_klasse

    @staticmethod
    def mu_unsigned(di, s, d, b, fsd, fcd, mr):
        #in: Bewehrungsdurchmesser di, Bewehrungsabstand s, Statische Höhe d, fsd, fcd, mr
        #out: mu, x, a_s, qs_klasse
        # units input: [m, m, m, m, N/m^2, N/m^2]
        a_s = np.pi * di ** 2 / (4 * s) * b  # [m^2]
        omega = a_s * fsd / (d * b * fcd)  # [-]
        mu = a_s * fsd * d * (1 - omega / 2)  # [Nm]
        x = omega * d / 0.85  # [m]
        if x / d <= 0.35 and mu >= mr:
            return mu, x, a_s, 1
        elif x / d <= 0.5 and mu >= mr:
            return mu, x, a_s, 2
        else:  # zero resistance for x/d>0.5
            epsilon = 1.0e-3
            shift = 0.5
            factor = 1 - 0.5 * (1 + 2 / np.pi * np.arctan((x/d - shift) / epsilon)) #irgendein Faktor, um die Funktion richtig auf 0 gehen zu lassen. Ist keine Formel aus irgendeiner Norm o.Ä., hat auch nichts mit der Statik zu tun#
            return factor*mu, x, a_s, 99  # Querschnitt hat ungenügendes Verformungsvermögen

    def calc_shear_resistance(self, d_installation=0.0):
        # in: self
        # out: Querkraftwiderstand positiv vu_p [N], Querkraftwiderstand negativ vu_n [N], Querkraftbewehrung as_bw [m2]
        #TODO: Anpassung an die SIA 262 (2025)! Ist noch gemäss alter Norm!
        di = self.bw_bg[0]      # diameter
        s = self.bw_bg[1]       # spacing
        n = self.bw_bg[2]       # number of stirrups per spacing
        fck = self.concrete_type.fck        #SIA 262
        fcd = self.concrete_type.fcd        #SIA 262
        tcd = self.concrete_type.tcd        #SIA 262
        dmax = self.concrete_type.dmax      #dmax in mm
        fsk = self.rebar_type.fsk           #SIA 262
        fsd = self.rebar_type.fsd           #SIA 262
        es = self.rebar_type.Es             #SIA 262
        bw = self.b         #Stegbreite
        d = self.d          #Statische Höhe für positives Biegemoment (untere Lagen)
        ds = self.ds        #Statische Höhe für negatives Biegemoment (obere Lagen)
        x_p = self.x_p      #Druckzonenhöhe positives Biegemoment (obere Querschnittsrand)
        x_n = self.x_n      #Druckzonenhöhe negatives Biegemoment (unterer Querschnittsrand)
        as_bw = self.calc_as_bw(di, n, s, d)
        if d_installation < d / 6:
            dv_p = d                    #Wirksame statische Höhe für Querkraft
        else:
            dv_p = d - d_installation   #Wirksame statische Höhe für Querkraft
        if d_installation < ds / 6:
            dv_n = ds                   #Wirksame statische Höhe für Querkraft
        else:
            dv_n = ds - d_installation  #Wirksame statische Höhe für Querkraft
        vu_p = self.vu_unsigned(bw, di, n, s, as_bw, d, dv_p, x_p, fck, fcd, tcd, fsk, fsd, es, dmax)   #Positiver Querkraftwiderstand [N]
        vu_n = self.vu_unsigned(bw, di, n, s, as_bw, ds, dv_n, x_n, fck, fcd, tcd, fsk, fsd, es, dmax)  #Negativer Querkraftwiederstand [N]
        return vu_p, vu_n, as_bw

    @staticmethod
    def calc_as_bw(di, n, s, d):
        #in: Bewehrungsduchmesser di [m], Anzahl Stäbe n [], Bewehrungsabstand s [m], Statische Höhe d [m]
        #out: Bewehrungsquerschnittsfläche Querkraftbewehrung as_bw [mm2]
        as_bw = np.pi * di ** 2 / 4 * n / s * 0.9*d #ToDo: muss die Bügelquerschnittsfläche nicht noch mit der Plattenstärke multipliziert werden?
        return as_bw

    @staticmethod
    def vu_unsigned(bw, di, n, s, as_bw, d, dv, x, fck, fcd, tcd, fsk, fsd, es, dmax=32, alpha=np.pi / 4, kc=0.55):
        rohw = as_bw / min(bw, 0.4)  # SIA 262, Zif. 5.5.2.2
        rohw_min = 0.001 * (fck * 1e-6 / 30) ** 0.5 * 500 / (fsk * 1e-6)  # SIA 262, Zif. 5.5.2.2
        s_max = 25*s  # SIA262, Zif. 5.5.2.2
        if bw < 0.5:  # SIA262, Zif. 5.5.2.3
            n_min = 2
        else:
            n_min = 4
        if rohw < rohw_min or s > s_max or n < n_min:  # cross-section resistance without stirrups
            ev = 1.5 * fsd / es         #SIA 262
            kg = 48 / (16 + dmax)       #SIA 262
            kd = 1 / (1 + ev * d * kg)  #SIA 262
            vrd = kd * tcd * dv
            return vrd #Querkraftwiderstand OHNE Querkraftbewehrung SIA 262
        else:  # cross-section resistance with vertical stirrups
            z = d - 0.85 * x / 2
            vrds = as_bw * z * fsd
            vrdc = bw * z * kc * fcd * np.sin(alpha) * np.cos(alpha)  # unit of alpha: [rad]
            return min(vrds, vrdc) #Querkraftwiderstand MIT Querkraftbewehrung SIA 262

    def calc_punching_shear_resistance(self, column_width=0.25, column_length=0.25, ke=0.9,
                                       l_x=None, l_y=None, m_ed=None, m_rd=None,
                                       rotation_factor=1.0, v_prestress=0.0):
        """
        Punching shear resistance according to SIA 262, level of approximation 2.

        Base concrete resistance without punching reinforcement:
            V_Rd,c(psi) = k_r * tau_cd * d_v * u
            k_r = 1 / (0.45 + 0.18 * psi * d_v[mm] * k_g) <= 2
            k_g = 48 / (16 + D_max)
            psi = 1.5 * r_s / d_v * f_sd / E_s * (m_sd / m_Rd) ** 1.5
            r_s = 0.22 * l
        """
        d_v = self.d
        u_1 = 2 * (column_width + column_length) + 2 * np.pi * d_v
        l_x = l_x if l_x is not None else d_v
        l_y = l_y if l_y is not None else l_x

        def as_pair(value, default):
            if value is None:
                return default
            if isinstance(value, (list, tuple, np.ndarray)):
                if len(value) >= 2:
                    return abs(value[0]), abs(value[1])
                if len(value) == 1:
                    return abs(value[0]), abs(value[0])
            value = abs(value)
            return value, value

        m_rd_default = max(abs(self.mu_max), abs(self.mu_min), 1e-9)
        m_ed_x, m_ed_y = as_pair(m_ed, (abs(self.mr_p), abs(self.mr_p)))
        m_rd_x, m_rd_y = as_pair(m_rd, (m_rd_default, m_rd_default))
        m_rd_x = max(m_rd_x, 1e-9)
        m_rd_y = max(m_rd_y, 1e-9)

        r_s_x = max(0.22 * l_x, d_v)
        r_s_y = max(0.22 * l_y, d_v)
        psi_x = 1.5 * r_s_x / d_v * self.rebar_type.fsd / self.rebar_type.Es * (m_ed_x / m_rd_x) ** 1.5
        psi_y = 1.5 * r_s_y / d_v * self.rebar_type.fsd / self.rebar_type.Es * (m_ed_y / m_rd_y) ** 1.5
        psi = rotation_factor * max(psi_x, psi_y)

        d_v_mm = d_v * 1e3
        k_g = 48 / (16 + self.concrete_type.dmax)
        k_r = min(2.0, 1 / (0.45 + 0.18 * psi * d_v_mm * k_g))
        v_rd_c = k_r * self.concrete_type.tcd * d_v * u_1
        v_rd_s = self.calc_punching_shear_reinforcement_resistance(d_v)
        v_rd_max = 2.0 * v_rd_c
        v_rd = min(v_rd_c + v_rd_s, v_rd_max)
        return max(v_rd * ke + v_prestress, 0)

    def calc_punching_shear_reinforcement_resistance(self, d_v):
        di, s, n = self.bw_bg
        if di <= 0 or s <= 0 or n <= 0:
            return 0.0
        reinforced_radius = 1.5 * d_v
        n_perimeters = max(math.floor(reinforced_radius / s), 1)
        a_sw = np.pi * di ** 2 / 4 * n * n_perimeters
        return a_sw * self.rebar_type.fsd

    @staticmethod
    def f_w_ger(roh, rohs, phi, h, d):
        f = (1 - 20 * rohs) / (10 * roh ** 0.7) * (0.75 + 0.1 * phi) * (h / d) ** 3
        #TODO: Prüfen, ob dieser Wert nicht zu konservativ ist! Als Abschätzung für die Vordimensionierung scheint der Wert jedoch schon i.O., ist zumindest nicht komplett willkürlich.
        return f

    @staticmethod
    def fire_resistance(section):
        # fire resistance of 1-D load-bearing plates according to SIA 262, Tab.16
        c_nom = section.c_nom
        h = section.h
        b = section.b
        if c_nom >= 0.04 and h >= 0.15 and b >= 0.4:
            resistance = 180
        elif c_nom >= 0.03 and h >= 0.12 and b >= 0.3:
            resistance = 120
        elif c_nom >= 0.03 and h >= 0.1 and b >= 0.2:
            resistance = 90
        elif c_nom >= 0.02 and h >= 0.08 and b >= 0.15:
            resistance = 60
        elif c_nom >= 0.02 and h >= 0.06 and b >= 0.1:
            resistance = 30
        else:
            resistance = 0
        return resistance
    
# ........................................................................
class PostTensionedConcrete(RectangularConcrete):
    # defines properties of rectangular, post-tensioned concrete cross-section
    def __init__(self, concrete_type, rebar_type, pt_steel_type, l_x, l_y, b, h, di_xu, s_xu, di_xo, s_xo,  di_yu=0.006, s_yu=0.15, di_yo=0.006, s_yo=0.15, di_bw=0.0, s_bw=0.15, n_bw=0,
                  phi=2.0, c_nom=0.02, xi=0.02, jnt_srch=0.1, layout=[1,0,1,0], c_nom_pt=0.03, A_p=150e-6,
                  compute_stiffness=True):
        # Only for rectangular plates l_x = l_y or l_y = 1 for beams  
        super().__init__(concrete_type, rebar_type, b, h, di_xu, s_xu, di_xo, s_xo, di_yu, s_yu, di_yo, s_yo, di_bw, s_bw, n_bw, phi, c_nom, xi, jnt_srch)
        self.section_type = "pc_rec"
        self.pt_steel_type = pt_steel_type
        self.A_p = A_p # cross-sectional area of post-tensioning tendon [m2]
        self.l_x = l_x # span in x direction [m]
        self.l_y = l_y # span in y direction [m]
        self.layout = layout #layout of post-tensioning tendons, 1: tendon present, 0: no tendon. Order of layout definition: [Drop beam x, Distributed x, Drop beam y , Distributed y]
        self.c_nom_pt = c_nom_pt #nominal cover for post-tensioning tendons [m]
        self.set_initial_pt_reinforcement()
        self.i = self.h**3/12 # moment of inertia of the plate [m4/m]
        tendon_info = self.update_prestressing_system()
        self.m_r = self.calc_mr_pt(self.Px_total,self.l_x)
        self.m_r_pt = self.m_r
        # The PT cracking moment is used for serviceability cracking/stiffness.
        # The minimum bonded reinforcement is only required to cover the ordinary
        # RC cracking moment; otherwise the prestress-induced compression forces
        # unrealistically drive very high passive reinforcement quantities.
        self.m_r_min_reinf = self.calc_mr_without_pt()
        self.mr_p, self.mr_n = self.m_r, -self.m_r
        bw = self.set_minimalReinforcement(self.m_r_min_reinf, use_pt=True)
        self.bw, self.d, self.ds = bw
        self.update_reinforcement_areas()
        # Cracked stiffness is only needed for serviceability checks. ULS optimisation
        # creates many trial sections, so skip the nonlinear solve there.
        if compute_stiffness:
            self.f_w_ger, self.ei2, self.ei1 = self.calc_EIeff(self.Px_total, self.l_x, 0, 0, self.m_r)
        else:
            self.ei1 = self.concrete_type.Ecm * self.i
            self.ei2 = self.ei1
            self.f_w_ger = 1.0

        # Moment resistance x direction
        [self.mu_max, self.x_p, self.as_p, self.qs_class_p] = self.calc_mu_pt(self.Px_total, self.l_x, 'pos')
        [self.mu_min, self.x_n, self.as_n, self.qs_class_n] = self.calc_mu_pt(self.Px_total, self.l_x, 'neg')

        # C02, cost and construction time per m2 of cross-section
        self.joint_surcharge = jnt_srch  # joint surcharge
        # Stagger shear reinforcement for material quantities; the resistance
        # model keeps the full local shear reinforcement, while GWP/cost use an
        # average amount over the slab area.
        volume_reinforcement = (self.as_p+self.as_n+self.as_yu+self.as_yo+0.5*self.as_bw/self.b)*(1 + self.joint_surcharge) # volume of reinforcement per m2 of cross-section [m3/m2] with joint surcharge
        volume_pt_steel = self.calc_pt_steel_volume_per_m2(tendon_info)
        volume_concrete = self.b*self.h - volume_reinforcement - volume_pt_steel # volume of concrete per m2 of cross-section [m3/m2]
        co2_rebar = volume_reinforcement * self.rebar_type.GWP * self.rebar_type.density  # [kg_CO2_eq/m]
        co2_pt_steel = volume_pt_steel * self.pt_steel_type.GWP * self.pt_steel_type.density  # [kg_CO2_eq/m]
        co2_concrete = volume_concrete * self.concrete_type.GWP * self.concrete_type.density  # [kg_CO2_eq/m]
        self.volume_reinforcement = volume_reinforcement
        self.volume_pt_steel = volume_pt_steel
        self.volume_concrete = volume_concrete
        self.g0k = self.calc_weight(volume_concrete, volume_reinforcement, volume_pt_steel)
        self.w = self.g0k
        self.co2_rebar = co2_rebar
        self.co2_pt_steel = co2_pt_steel
        self.co2_concrete = co2_concrete
        self.cost_rebar = volume_reinforcement * self.rebar_type.cost
        self.cost_concrete = volume_concrete * self.concrete_type.cost + self.concrete_type.cost2
        self.cost_pt_steel = volume_pt_steel * self.pt_steel_type.cost
        self.co2 = co2_rebar + co2_concrete + co2_pt_steel # [kg_CO2_eq/m]
        self.cost = volume_reinforcement * self.rebar_type.cost + volume_concrete * self.concrete_type.cost + volume_pt_steel * self.pt_steel_type.cost + self.concrete_type.cost2# [CHF/m]
        self.construction_time = volume_reinforcement * self.rebar_type.construction_time + volume_concrete * self.concrete_type.construction_time + volume_pt_steel * self.pt_steel_type.construction_time  + self.concrete_type.construction_time_scaffold # [h/m]

    def set_punching_reinforcement_volume(self, volume):
        super().set_punching_reinforcement_volume(volume)
        
    def set_initial_pt_reinforcement(self):
        # Simplified PT layout assumption: use the same minimum bonded
        # reinforcement diameter as ordinary RC before determining tendon
        # eccentricity and force. The minimum-reinforcement check below may
        # still increase the diameter if the cracking-moment target requires it.
        for layer in self.bw:
            layer[0] = max(layer[0], 0.006)
        self.d, self.ds = self.calc_d()
        self.update_reinforcement_areas()

    def update_reinforcement_areas(self):
        self.as_p = (np.pi*self.bw[0][0]**2/4/self.bw[0][1]) # as for positive bending (lower layers) [m2/m]
        self.as_n = (np.pi*self.bw[1][0]**2/4/self.bw[1][1]) # as for negative bending (upper layers) [m2/m]
        self.as_yu = (np.pi*self.bw[2][0]**2/4/self.bw[2][1]) # as for lower y reinforcement [m2/m]
        self.as_yo = (np.pi*self.bw[3][0]**2/4/self.bw[3][1]) # as for upper y reinforcement [m2/m]
        self.roh, self.rohs = self.as_p / self.d, self.as_n / self.ds

    def calc_mr_without_pt(self):
        return self.b * self.h ** 2 / 6 * 1.3 * self.concrete_type.fctm

    def calc_pt_steel_volume_per_m2(self, tendon_info):
        # Tendon quantities are stored as tendon counts per distributed metre
        # or per support strip. For material quantities, the tendon length has to
        # be included. Distributed tendons therefore contribute n*A_p per m2,
        # while support-strip tendons contribute n*A_p/l_perpendicular.
        n_drop_x = tendon_info['drop_beam_x']['n_tendons']
        n_dist_x = tendon_info['distributed_x']['n_tendons']
        n_drop_y = tendon_info['drop_beam_y']['n_tendons']
        n_dist_y = tendon_info['distributed_y']['n_tendons']
        return (
            n_dist_x * self.A_p
            + n_dist_y * self.A_p
            + n_drop_x * self.A_p / max(self.l_y, 1e-9)
            + n_drop_y * self.A_p / max(self.l_x, 1e-9)
        )

    def update_prestressing_system(self):
        self.e_support, self.e_midspan, self.dp = self.calc_eccentricity()  # eccentricity of post-tensioning tendons [m]
        self.f = self.e_midspan - self.e_support #Pfeilhöhe
        self.f_x = self.f
        self.f_y = self.f
        tendon_info = self.set_loadBalancing() # post-tensioning forces [N]
        self.Psx = tendon_info['drop_beam_x']['force'] # post-tensioning force in drop beam in x direction [N]
        self.pdx = tendon_info['distributed_x']['force'] # distributed post-tensioning force in x direction [N/m]
        self.Psy = tendon_info['drop_beam_y']['force'] # post-tensioning force in drop beam in y direction [N]
        self.pdy = tendon_info['distributed_y']['force'] # distributed post-tensioning force in y direction [N/m]
        self._secondary_internal_forces_cache = {}
        self.Px_total = self.Psx + self.pdx*self.l_x
        self.Py_total = self.Psy + self.pdy*self.l_y
        return tendon_info


    def calc_eccentricity(self):
        # in: self, A_p (cross-sectional area of post-tensioning tendon [m2])
        # out: eccentricity of post-tensioning tendons at supports and midspan [m]
        r_P = np.sqrt(self.A_p / np.pi)  # radius of post-tensioning tendon [m]
        e_support = -(self.h / 2 - max(self.c_nom_pt, -(self.c_nom + self.bw[1][0] + self.bw[3][0] + self.bw_bg[0])) - r_P)
        e_midspan = (self.h / 2 - max(self.c_nom_pt, -(self.c_nom + self.bw[0][0] + self.bw[2][0] + self.bw_bg[0])) - r_P)
        dp = self.h / 2 + abs(e_midspan) # distance from the top/bottom of the cross-section to the centroid of the post-tensioning tendons [m]
        return e_support, e_midspan, dp
        
    def set_minimalReinforcement(self, target_mr=None, use_pt=False):
        # Keep the reinforcement chosen by the optimizer, but enforce a minimal bonded
        # reinforcement for robustness of unbonded PT slabs.
        self.minimal_reinforcement_ok = True
        for layer in self.bw:
            layer[0] = max(layer[0], 0.006)

        self.d, self.ds = self.calc_d()

        mr_pos = abs(target_mr) if target_mr is not None else abs(self.mr_p)
        mr_neg = abs(target_mr) if target_mr is not None else abs(self.mr_n)
        layer_pairs = ((0, 2, mr_pos, "pos"), (1, 3, mr_neg, "neg"))
        for idx_x, idx_y, mr, sign in layer_pairs:
            while True:
                d_eff = self.d if sign == "pos" else self.ds
                if use_pt:
                    self.update_reinforcement_areas()
                    mu = abs(self.calc_mu_pt(self.Px_total, self.l_x, sign)[0])
                else:
                    mu = self.mu_unsigned(
                        self.bw[idx_x][0], self.bw[idx_x][1], d_eff, self.b,
                        self.rebar_type.fsd, self.concrete_type.fcd, mr
                    )[0]
                if mu >= mr:
                    break
                if self.bw[idx_x][0] >= 0.04:
                    self.minimal_reinforcement_ok = False
                    break
                self.bw[idx_x][0] = min(self.bw[idx_x][0] + 0.002, 0.04)
                self.bw[idx_y][0] = self.bw[idx_x][0]
                self.d, self.ds = self.calc_d()
        return self.bw, self.d, self.ds

    def set_loadBalancing(self, degree_of_posttensioning=0.7, longterm_losses=0.15):
        V_p = self.g0k * self.l_x * self.l_y
        u_0 = V_p / (self.l_x * self.l_y)  # average deviation force on slab [N/m2]
        Psx, pdx, Psy, pdy = 0, 0, 0, 0
        if self.layout[3] == 1:  # distributed in y direction
            if self.layout[1] == 1:  # distributed in x and y direction
                u_x = u_0 / 2  # deviation force in x direction [N/m2]
                u_y = u_0 / 2  # deviation force in y direction [N/m2]
                pdx = u_x * self.l_x**2 / (8 * self.f_x)  # post tensioning force distributed tendons in x direction [N]
                pdy = u_y * self.l_y**2 / (8 * self.f_y)  # post tensioning force distributed tendons in y direction [N]
                if self.layout[0] == 1:  # drop beam in x direction
                    Psx = u_y * self.l_y * self.l_x**2 / (8 * self.f_x)  # post tensioning force in drop beam in x direction [N]
                if self.layout[2] == 1:  # drop beam in y direction
                    Psy = u_x * self.l_x * self.l_y**2 / (8 * self.f_y)  # post tensioning force in drop beam in y direction [N]
            else:  # distributed only in y direction
                u_y = u_0  # deviation force in y direction [N/m2]
                pdx = 0
                pdy = u_y * self.l_y**2 / (8 * self.f_y)  # post tensioning force distributed tendons in y direction [N]
                if self.layout[0] == 1:  # drop beam in x direction
                    Psx = u_y * self.l_y * self.l_x**2 / (8 * self.f_x)  # post tensioning force in drop beam in x direction [N]
        else:  # no distributed tendons
            if self.layout[0] == 1:  # drop beam in x direction
                if self.layout[2] == 1:  # drop beam in x and y direction
                    # Px and Py are equal (rectangular slab layout)
                    Psx = V_p / 2 * self.l_x / (8 * self.f_x)  # l_x and l_y are equal for rectangular slab layout
                    Psy = V_p / 2 * self.l_y / (8 * self.f_y)  # l_x and l_y are equal for rectangular slab layout

        # Algorithmus to find the number of tendons and their degree of post tensioning within the limits
        def find_n_and_degree(P_req):
            if P_req == 0:
                return 0, 0

            alpha_max = degree_of_posttensioning
            alpha_min = max(0.0, degree_of_posttensioning - 0.1)
            p_tendon = (1 - longterm_losses) * self.pt_steel_type.fpk * self.A_p

            n_min = max(math.ceil(P_req / (alpha_max * p_tendon)), 1)
            n_max = max(math.floor(P_req / (alpha_min * p_tendon)), n_min) if alpha_min > 0 else n_min

            candidates = range(n_min, n_max + 1)
            n = min(candidates, key=lambda n_i: abs(P_req / (n_i * p_tendon) - degree_of_posttensioning))
            alpha = P_req / (n * p_tendon)
            return n, alpha

        # Find number of tendons and degree of post-tensioning for each tendon group
        n_psx, alpha_psx = find_n_and_degree(Psx)
        n_pdx, alpha_pdx = find_n_and_degree(pdx)
        n_psy, alpha_psy = find_n_and_degree(Psy)
        n_pdy, alpha_pdy = find_n_and_degree(pdy)

        # Build array for returning the results
        tendon_info = {
            'drop_beam_x': {'force': Psx, 'n_tendons': n_psx, 'alpha': alpha_psx},
            'distributed_x': {'force': pdx, 'n_tendons': n_pdx, 'alpha': alpha_pdx},
            'drop_beam_y': {'force': Psy, 'n_tendons': n_psy, 'alpha': alpha_psy},
            'distributed_y': {'force': pdy, 'n_tendons': n_pdy, 'alpha': alpha_pdy}
        }

        return tendon_info

    def calc_mr_pt(self, P_total, l):
        # in: self
        # out: cracking moment mr_pt at points of maximum eccentricity [Nm]
        fctm_eff = max((1.6 - self.h) * self.concrete_type.fctm, self.concrete_type.fctm)  # effective tensile strength of concrete
        e_max = max(abs(self.e_support), abs(self.e_midspan))  # maximum eccentricity of post-tensioning tendons [m] (should be same at support and midspan)
        sigma_c_inf = -P_total / l / self.h - P_total * e_max * self.h / 2 / self.i  # average compressive stress in concrete due to post-tensioning force [N/m2/]
        mr_pt = (fctm_eff - sigma_c_inf) * self.i / (self.h / 2)  # cracking moment at points of maximum eccentricity [Nm]
        return mr_pt  # [Nm/m']

    def calc_EIeff(self, P_total, l, MEd_SLS, M_sec, m_r):
        # in: self
        # out: f (factor cracked/uncracked), cracked bending stiffness, uncracked bending stiffness
        E_c = self.concrete_type.Ecm  # effective modulus of elasticity of concrete (creep is considered in member)
        EI_uncracked_inf = E_c * self.i  # bending stiffness of uncracked section [Nm2/m]
        m_eff = abs(MEd_SLS + M_sec)
        if m_r <= 0 or m_eff <= m_r:
            return 1.0, EI_uncracked_inf, EI_uncracked_inf

        zeta = max(0.0, min(1.0, 1 - 0.5 * (m_r / m_eff)**2))  # degree of partial cracking
        # Solve set of equations: three equations for three unknowns
        # 1) Moment equilibrium: self.d*self.as_p*sigma_s + self.dp*P_total/l + MEd_SLS + M_sec = b*x_II**2/6*sigma_c_inf.
        # 2) Force equilibrium: self.as_p*sigma_s + P_total/l = b*x_II/2*sigma_c_inf
        # 3) Compatibility 1: sigma_s = e_c_inf/x_II*(self.ds-x_II)*self.rebar_type.Es
        # 4) Compatibility 2: sigma_c_inf = self.concrete_type.Ecm*e_c_inf
        # Solve for x_II
        def equations(vars):
            x_II, sigma_s, sigma_c_inf = vars
            e_c_inf = sigma_c_inf / self.concrete_type.Ecm
            eq1 = (
                self.d * self.as_p * sigma_s
                + self.dp * P_total / l
                + MEd_SLS
                + M_sec
                - self.b * x_II**2 / 6 * sigma_c_inf
            )
            eq2 = (
                self.as_p * sigma_s
                + P_total / l
                - self.b * x_II / 2 * sigma_c_inf
            )
            eq3 = sigma_s - (
                e_c_inf / x_II * (self.ds - x_II) * self.rebar_type.Es
            )
            return [eq1, eq2, eq3]

        # Initial guesses
        x_II_guess = self.d * 0.4
        sigma_s_guess = self.rebar_type.fsd * 0.5
        sigma_c_inf_guess = self.concrete_type.fcd * 0.3

        # Bounds
        lower_bounds = [1e-6, 0, 0]
        upper_bounds = [self.d, self.rebar_type.fsd, self.concrete_type.fcd]

        solution = least_squares(
            equations,
            x0=[x_II_guess, sigma_s_guess, sigma_c_inf_guess],
            bounds=(lower_bounds, upper_bounds),
            x_scale=[max(self.d, 1e-3), max(self.rebar_type.fsd, 1.0), max(self.concrete_type.fcd, 1.0)],
            ftol=1e-5,
            xtol=1e-5,
            gtol=1e-5,
            max_nfev=40,
        )

        x_II = solution.x[0]
        EI_cracked_inf = E_c * (x_II**3 / 3 + self.rebar_type.Es / self.concrete_type.Ecm * self.as_p * (self.ds - x_II)**2)  # Bending stiffness of cracked section [Nm2/m]
        EIeff_inf = zeta * EI_uncracked_inf + (1 - zeta) * EI_cracked_inf  # Effective bending stiffness considering partial cracking [Nm2/m]

        f = EIeff_inf / EI_uncracked_inf
        return f, EIeff_inf, EI_uncracked_inf

    def calc_mu_pt(self, P_total, l, sign='pos'):
        # in: self
        # out: Biegewiderstand mu [Nm], Druckzonenhöhe x [m], Bewehrungsfläche a_s [m2], Querschnittsklasse qs_klasse []
        fpd = self.pt_steel_type.fpd
        fsd = self.rebar_type.fsd
        fcd = self.concrete_type.fcd
        dp = self.dp
        ds = self.ds
        if sign == 'pos':
            di = self.bw[0][0]
            s = self.bw[0][1]
            [mu, x, a_s, qs_klasse] = self.mu_unsigned_pt(P_total, l, fpd, fsd, fcd, dp, self.d, di, s)
        elif sign == 'neg':
            di = self.bw[1][0]
            s = self.bw[1][1]
            [mus, x, a_s, qs_klasse] = self.mu_unsigned_pt(P_total, l, fpd, fsd, fcd, dp, ds, di, s)
            mu = -mus
        else:
            [mu, x, a_s, qs_klasse] = [0, 0, 0, 0]
            print("sign of moment resistance has to be 'neg' or 'pos'")
        min_reinf_mr = abs(getattr(self, "m_r_min_reinf", self.m_r))
        if abs(mu) < min_reinf_mr:
            qs_klasse = 99
        return mu, x, a_s, qs_klasse

    def calc_punching_shear_resistance(self, column_width=0.25, column_length=0.25, ke=0.9,
                                       l_x=None, l_y=None, m_ed=None, m_rd=None,
                                       rotation_factor=1.0, v_prestress=0.0):
        v_prestress += self.calc_punching_prestress_deviation_force(column_width, column_length)
        return super().calc_punching_shear_resistance(
            column_width=column_width,
            column_length=column_length,
            ke=ke,
            l_x=l_x,
            l_y=l_y,
            m_ed=m_ed,
            m_rd=m_rd,
            rotation_factor=rotation_factor,
            v_prestress=v_prestress,
        )

    def calc_punching_prestress_deviation_force(self, column_width, column_length):
        d_v = self.d
        control_width_x = column_width + 2 * d_v
        control_width_y = column_length + 2 * d_v
        sin_beta_x, sin_beta_y = self.calc_prestress_sin_beta()
        p_x_distributed = self.pdx * control_width_y
        p_y_distributed = self.pdy * control_width_x
        return max((self.Psx + p_x_distributed) * sin_beta_x + (self.Psy + p_y_distributed) * sin_beta_y, 0.0)

    def calc_prestress_deviation_loads(self):
        # Equivalent upward load for parabolic tendons: u = 8 * P * f / L^2.
        p_x = self.Psx / max(self.l_y, 1e-9) + self.pdx
        p_y = self.Psy / max(self.l_x, 1e-9) + self.pdy
        u_x = 8 * p_x * self.f / max(self.l_x ** 2, 1e-9)
        u_y = 8 * p_y * self.f / max(self.l_y ** 2, 1e-9)
        return max(u_x, 0.0), max(u_y, 0.0)

    def calc_prestress_shear_deviation_force(self, direction="x"):
        sin_beta_x, sin_beta_y = self.calc_prestress_sin_beta()
        if direction == "y":
            return (self.Psy / max(self.l_x, 1e-9) + self.pdy) * sin_beta_y
        return (self.Psx / max(self.l_y, 1e-9) + self.pdx) * sin_beta_x

    def calc_prestress_sin_beta(self):
        sin_beta_x = 4 * self.f / max(self.l_x, 1e-9)
        sin_beta_y = 4 * self.f / max(self.l_y, 1e-9)
        return sin_beta_x, sin_beta_y
    
    def get_secondaryInternalForces(self, system):
        # in: self, system (structural system of the member)
        # out: secondary moments [Nm/m'] or secondary shear forces [N/m] 
        cache_key = (system.raender, system.lx, system.ly)
        if cache_key in self._secondary_internal_forces_cache:
            return self._secondary_internal_forces_cache[cache_key]

        #Check whether there are drop beams
        M_sec_x = np.array([0.0, 0.0]) # secondary moments positive and negative bending x direction [Nm/m']
        M_sec_y = np.array([0.0, 0.0]) # secondary moments positive and negative bending y direction [Nm/m']
        V_sec = np.array([0.0, 0.0]) # secondary shear forces in pos and neg [N/m]

        if self.layout[0] == 1 or self.layout[2] == 1:
            # Initialize slab system with drop beams
            system_drop = Slab(self.l_x, self.l_y, "drop_beam")
            # get alphas
            alpha_m_x = np.array(system_drop.alpha_m_x) #[pos,neg] bending in x direction
            alpha_m_y = np.array(system_drop.alpha_m_y) #[pos,neg] bending in y direction
            alpha_v = np.array(system_drop.alpha_v) #[pos,neg] shear forces
            # Calculate total moments and shear forces due to post-tensioning in drop beams
            # Post tensioning acts upwards: Field moment negative, support moment positive
            M_sec_x += 8*self.Psx * self.f * -alpha_m_x # secondary moment in x direction due to drop beam post-tensioning force [Nm/m'], - as post tensioning acts upwards
            M_sec_y += 8*self.Psy * self.f * -alpha_m_y # secondary moment in y direction due to drop beam post-tensioning force [Nm/m'], - as post tensioning acts upwards
            V_sec += 8*self.Psx * self.f / self.l_x * -alpha_v # secondary shear force (in x direction) due to drop beam post-tensioning force [N/m]

        # get alphas of the true system for uniform distributed load
        alpha_m_x = np.array(system.alpha_m_x)
        alpha_m_y = np.array(system.alpha_m_y)
        alpha_v = np.array(system.alpha_v)
        
        # Calculate total moments and shear forces due to post-tensioning in drop beams
        M_sec_x += 8*self.pdx * self.f * -alpha_m_x # secondary moment in x direction due to distributed post-tensioning force [Nm/m']
        M_sec_y += 8*self.pdy * self.f * -alpha_m_y # secondary moment in y direction due to distributed post-tensioning force [Nm/m']
        V_sec += 8*self.pdx * self.f / self.l_x * -alpha_v # secondary shear force (in x direction) due to distributed post-tensioning force [N/m]

        # Save total moments and shear forces for post-tensioning
        M_tot_x = M_sec_x.copy() # total moment in x direction due to post-tensioning force [Nm/m']
        M_tot_y = M_sec_y.copy() # total moment in y direction due to post-tensioning force [Nm/m']
        V_tot = V_sec.copy() # total shear force in x direction due to post-tensioning force [N/m]

        #Secondary moments are M_sec = M_tot - P*e and V_sec = V_tot - P*de/dx
        M_sec_x[0] = M_tot_x[0] - self.Px_total/self.l_x * self.e_midspan # secondary moment at midspan in x direction [Nm/m']
        M_sec_x[1] = M_tot_x[1] - self.Px_total/self.l_x * self.e_support # secondary moment at support in x direction [Nm/m']
        M_sec_y[0] = M_tot_y[0] - self.Py_total/self.l_y * self.e_midspan # secondary moment at midspan in y direction [Nm/m']
        M_sec_y[1] = M_tot_y[1] - self.Py_total/self.l_y * self.e_support # secondary moment at support in y direction [Nm/m']
        V_sec[0] = V_tot[0] + self.Px_total/self.l_x * 4*self.f/self.l_x # secondary shear force [N/m]
        V_sec[1] = V_tot[1] - self.Px_total/self.l_x * 4*self.f/self.l_x # secondary shear force [N/m]


        result = (M_sec_x.tolist(), M_sec_y.tolist(), V_sec.tolist())
        self._secondary_internal_forces_cache[cache_key] = result
        return result

    @staticmethod
    def mu_unsigned_pt(P_total, l, fpd, fsd, fcd, dp, ds, dis, s):
        # in: Total post tensioning force in one direction [N], l span in this direction, fpd design post tensioning strength [N/m2], fsd design reinforcement strength [N/m2]), fcd concrete compressive strength, dp static dept of tendons [m]), ds static dept of reinforcement [m], dis diameter of reinforcement[m], s spacing of reinforcement [m], Ap cross-sectional area of post-tensioning tendon [m2])
        # out: mu, x, a_s, qs_klasse
        # units input: [m, m, m, m, N/m^2, N/m^2]
        a_s = np.pi * dis**2 / (4 * s)  # [m^2/m']
        x = (a_s * fsd + P_total / l) / (fcd * 1)  # Druckzonenhöhe [m]
        mu = P_total / l * (dp - 0.85 * x / 2) + a_s * fsd * (ds - 0.85 * x / 2)  # Biegewiderstand [Nm/m']
        a_p = P_total / l / fpd  # equivalent prestressing steel area per metre [m2/m]
        d_avg = (a_p * dp + a_s * ds) / max(a_p + a_s, 1e-12)  # average static height of the tensile reinforcement [m]
        if x / d_avg <= 0.35:
            return mu, x, a_s, 1
        elif x / d_avg <= 0.5:
            return mu, x, a_s, 2
        else:  # zero resistance for x/d>0.5
            epsilon = 1.0e-3
            shift = 0.5
            factor = 1 - 0.5 * (1 + 2 / np.pi * np.arctan((x / d_avg - shift) / epsilon))  # irgendein Faktor, um die Funktion richtig auf 0 gehen zu lassen. Ist keine Formel aus irgendeiner Norm o.Ä., hat auch nichts mit der Statik zu tun
            return factor * mu, x, a_s, 99  # Querschnitt hat ungenügendes Verformungsvermögen

    @staticmethod
    def fire_resistance(section):
        # fire resistance of 1-D load-bearing plates according to SIA 262, Tab.16
        c_nom = section.c_nom
        c_nom_pt = section.c_nom_pt
        h = section.h
        b = section.b
        if c_nom >= 0.04 and c_nom_pt >= 0.06 and h >= 0.15 and b >= 0.4:
            resistance = 180
        elif c_nom >= 0.03 and c_nom_pt >= 0.045 and h >= 0.12 and b >= 0.3:
            resistance = 120
        elif c_nom >= 0.03 and c_nom_pt >= 0.045 and h >= 0.1 and b >= 0.2:
            resistance = 90
        elif c_nom >= 0.02 and c_nom_pt >= 0.03 and h >= 0.08 and b >= 0.15:
            resistance = 60
        elif c_nom >= 0.02 and c_nom_pt >= 0.03 and h >= 0.06 and b >= 0.1:
            resistance = 30
        else:
            resistance = 0
        return resistance

# ........................................................................

class SupStrucRibbedConcrete(Section):
    def __init__(self, section_type, b, b_w, h, h_f, l0, phi=0):
        super().__init__(section_type)
        self.b = b              # flange width [m] (Abstand Rippenachse-Rippenachse)
        self.b_w = b_w          # web width [m]
        self.h = h              # total height [m]
        self.h_f = h_f          # flange height [m]
        self.h_w = h - h_f      # web height [m]
        self.l0 = l0            # Abstand Momentennullpunkte [m]
        self.b_eff = self.calc_beff()               #Effective width [m]
        self.a_brutt = self.calc_area()             #Bruttoquerschnittsfläche [m2]
        self.z_s = self.calc_center_of_gravity()    #center of gravity [m]
        self.iy = self.calc_moment_of_inertia()     #moment of inertia [m4]
        self.w = 0.0
        self.phi = phi                              #Kriechzahl

    def calc_area(self):
        # in: width b and bw [m], height h and h_f[m]
        # out: area [m2]
        a_brutt = self.b * self.h_f + self.b_w * self.h_w
        return a_brutt

    def calc_beff(self):
        # in: width b [m], bw [m], l_0 [m]
        # out: effective width b_eff
        l_0 = self.l0
        b_eff_i = 0.2 * (self.b - self.b_w) / 2 + 0.1 * l_0  # SIA 262, 4.1.3.3.2 (20)
        if b_eff_i > 0.2 * l_0:
            b_eff_i = 0.2 * l_0
        else:
            pass
        b_eff = 2 * b_eff_i + self.b_w  # SIA 262, 4.1.3.3.2 (19)
        if b_eff > self.b:
            b_eff = self.b
        else:
            pass
        return b_eff

    def calc_center_of_gravity(self):
        # in: Geometry effective width b_eff [m], slab height h_f [m], rib width b_w [m], rib height h_w [m]
        # out: center of gravity z_s [m], z = 0: OK Slab
        z_s = (self.b_eff * self.h_f ** 2 / 2 + self.b_w * self.h_w * (self.h_f +self.h_w/2)) / (
                    self.b_eff * self.h_f + self.b_w * self.h_w)
        return z_s

    def calc_moment_of_inertia(self):
        # in: Geometry effective width b_eff [m], slab height h_f [m], rib width b_w [m], rib height h_w [m], center of gravity z_s [m]
        # out: moment of inertia I_y [m^4]
        i_01 = self.b_eff * self.h_f ** 3 / 12
        as_01 = self.b_eff * self.h_f * abs(self.z_s - self.h_f / 2) ** 2
        i_02 = self.b_w * self.h_w ** 3 / 12
        as_02 = self.b_w * self.h_w * abs(self.z_s - (self.h_f + self.h_w/2)) ** 2
        iy = i_01 + i_02 + as_01 + as_02
        return iy

    #def calc_strength_elast(self, fy, ty):
    #def calc_strength_plast(self, fy, ty):

    def calc_weight(self, material):
        #  out: product-specific concrete weight per m length before reinforcement correction [N/m]
        return material.specific_weight * self.a_brutt


#.....................................................................................
class RibbedConcrete(SupStrucRibbedConcrete):
    #defines properties of a rectangular, reinforced concrete section
    #di_x_w, n_x_w = diameter and number of longitudinal reinforcement in rib
    def __init__(self, concrete_type, rebar_type, l0, b, b_w, h, h_f, di_xu, s_xu, di_xo, s_xo, di_x_w, n_x_w,
                 di_pb_bw, s_pb_bw, n_pb_bw=2,
                 phi=2.0, c_nom=0.03, xi=0.02, jnt_srch=0.15):
        section_type = "rc_rib"
        super().__init__(section_type, b, b_w, h, h_f, l0, phi)
        self.concrete_type = concrete_type
        self.rebar_type = rebar_type
        self.w = 0.0
        self.c_nom = c_nom
        self.bw = [[di_xu, s_xu], [di_xo, s_xo]]  # Slab reinforcement
        self.bw_bg = [0, 0.15, 0]  # Allow for no slab shear reinforcement
        self.bw_r = [di_x_w, n_x_w]  # Longitudinal reinforcement in rib
        self.bw_bg_r = [di_pb_bw, s_pb_bw, n_pb_bw]  # Shear reinforcement in rib
        mr_slab = self.b * self.h ** 2 / 6 * 1.3 * self.concrete_type.fctm  # cracking moment
        mr_pb = self.iy / (self.h - self.z_s) * 1.3 * self.concrete_type.fctm  # cracking moment
        self.mr_p, self.mr_n = mr_slab, -mr_slab
        self.mr_pb_p = mr_pb
        self.mr_pb_n = -mr_pb
        [self.d, self.ds, self.d_PB, self.ds_PB] = self.calc_d()
        [self.mu_max_slab, self.x_p, self.as_p, self.qs_class_p_slab] = self.calc_mu('pos')
        [self.mu_min_slab, self.x_n, self.as_n, self.qs_class_n_slab] = self.calc_mu('neg')
        [self.mu_max, self.x_PB_p, self.as_PB_p, self.qs_class_p] = self.calc_mu_pb('pos')
        [self.mu_min, self.x_PB_n, self.as_PB_n, self.qs_class_n] = self.calc_mu_pb('neg')
        self.roh_slab, self.rohs, self.roh = self.as_p / self.d, self.as_n / self.ds, self.as_PB_p / self.d_PB
        [self.vu_p, self.vu_n, self.as_bw] = self.calc_shear_resistance('Platte')  #Platte "Querrichtung"
        [self.vu_PB_p, self.vu_PB_n, self.as_PB_bw] = self.calc_shear_resistance(
            'Plattenbalken')  #Rippe Plattenbalken "Längsrichtung"
        # Slab reinforcement is counted over the full rib spacing. The negative
        # PB resistance also uses the upper slab reinforcement, so it is not
        # counted a second time as rib reinforcement.
        a_s_slab = self.as_p + self.as_n + 0.5 * self.as_bw
        a_s_rib = self.as_PB_p + 0.5 * self.as_PB_bw
        #TODO: Achtung - es fehlt die Spreizbewehrung
        # Assumption here hardcoded as d=12mm @ 150
        a_s_spreibewehrung = 2*np.pi*0.012**2/4/0.15 # 2-lagig[m2/m]
        a_s_slab += a_s_spreibewehrung
        ###########

        self.joint_surcharge = jnt_srch
        a_s_tot = (a_s_slab * self.b + a_s_rib) * (1 + self.joint_surcharge)
        concrete_area = max(self.a_brutt - a_s_tot, 0.0)
        self.g0k = self.calc_weight(concrete_area, a_s_tot)
        self.w = self.g0k / self.b
        co2_rebar = a_s_tot * self.rebar_type.GWP * self.rebar_type.density  # [kg_CO2_eq/m]
        co2_concrete = concrete_area * self.concrete_type.GWP * self.concrete_type.density  # [kg_CO2_eq/m]
        self.volume_reinforcement = a_s_tot / self.b
        self.volume_concrete = concrete_area / self.b
        self.volume_pt_steel = 0.0
        self.co2_rebar = co2_rebar / self.b
        self.co2_concrete = co2_concrete / self.b
        self.co2_pt_steel = 0.0
        self.cost_rebar = a_s_tot * self.rebar_type.cost / self.b
        formwork_factor = 2 * (self.b + 2 * self.h_f) / self.b # 2* accounts for additional complexity and decreased reuse of formwork for ribbed slabs compared to flat slabs. 
        formwork_cost = self.concrete_type.cost2 * formwork_factor
        formwork_time = self.concrete_type.construction_time_scaffold * formwork_factor
        self.cost_concrete = concrete_area * self.concrete_type.cost / self.b + formwork_cost
        self.cost_pt_steel = 0.0
        self.ei1 = self.concrete_type.Ecm * self.iy  # elastic stiffness concrete (uncracked behaviour) [Nm^2]
        self.co2 = (co2_rebar + co2_concrete)/self.b
        self.cost = (a_s_tot * self.rebar_type.cost + concrete_area * self.concrete_type.cost)/self.b + formwork_cost # [CHF/m]
        self.construction_time = (a_s_tot * self.rebar_type.construction_time + concrete_area * self.concrete_type.construction_time)/self.b + formwork_time # [h/m]
        self.ei_b = self.ei1  #!!!!!!!ANPASSEN AUF PB
        self.xi = xi  # XXXXXXX preset value is an assumption. Has to be verified with literature. XXXXXXX
        self.ei2 = self.ei1 / self.f_w_ger(self.roh, self.rohs, 0, self.h, self.d_PB)  #!!!!!ANPASSEN AUF PB
        self.h_installation = self.h_w # height available for installation of services. 

    def calc_weight(self, concrete_area=None, reinforcement_area=0.0):
        #  out: product-specific ribbed RC weight per rib spacing [N/m]
        concrete_area = self.a_brutt if concrete_area is None else max(concrete_area, 0.0)
        return (
            self.concrete_type.specific_weight * concrete_area
            + self.rebar_type.specific_weight * max(reinforcement_area, 0.0)
        )

    def calc_d(self):
        d = self.h_f - self.c_nom - self.bw[0][0] / 2  # Statische Höhe 1. Lage Platte
        ds = self.h_f - self.c_nom - self.bw[1][0] / 2  # Statische Höhe 4. Lage Platte
        d_PB = self.h - self.c_nom - self.bw_bg_r[0] - self.bw_r[
            0] / 2  # Nur eine Lage Längsbewehrung implementiert. ACHTUNG: Check implementieren, ob genug Platz für Längsbewehrung vorhanden!!
        ds_PB = self.h - self.c_nom - self.bw[1][0]  # Mittlere statische Höhe 3./4. Lage Platte
        return d, ds, d_PB, ds_PB

    #Slab = Platte in Querrichtung. ACHTUNG: DURCHLAUFWIRKUNG MUSS NOCH IMPLEMENTIERT WERDEN!
    #Kann man die Berechnung der Platte zusammenführen mit Rectangular Concrete?

    def calc_mu(self, sign='pos'):
        # calculates moment resistence of slab
        b = 1
        fsd = self.rebar_type.fsd
        fcd = self.concrete_type.fcd
        if sign == 'pos':
            [mu, x, a_s, qs_klasse] = self.mu_unsigned(self.bw[0][0], self.bw[0][1], self.d, b, fsd, fcd, self.mr_p)
        elif sign == 'neg':
            [mus, x, a_s, qs_klasse] = self.mu_unsigned(self.bw[1][0], self.bw[1][1], self.ds, b, fsd, fcd, self.mr_n)
            mu = -mus
        else:
            [mu, x, a_s, qs_klasse] = [0, 0, 0, 0]
            print("sign of moment resistance has to be 'neg' or 'pos'")

        return mu, x, a_s, qs_klasse

    def calc_mu_pb(self, sign='pos'):
        # calculates moment resistence of Plattenbalken = PB
        fsd = self.rebar_type.fsd
        fcd = self.concrete_type.fcd
        if sign == 'pos':
            [mu_PB, x, a_s, qs_klasse] = self.mu_unsigned_PB(self.bw_r[0], self.bw_r[1], self.d_PB, self.b_eff,
                                                             self.h_f, fsd, fcd, self.mr_pb_p)
        elif sign == 'neg':
            [mus_PB, x, a_s, qs_klasse] = self.mu_unsigned_different_widths(
                self.bw[1][0],
                self.bw[1][1],
                self.ds_PB,
                self.b_eff,
                self.b_w,
                fsd,
                fcd,
                self.mr_pb_n,
            )
            mu_PB = - mus_PB
        else:
            [mu_PB, x, a_s, qs_klasse] = [0, 0, 0, 0]
            print("sign of moment resistance has to be 'neg' or 'pos'")

        return mu_PB, x, a_s, qs_klasse

    @staticmethod
    def mu_unsigned(di, s, d, b, fsd, fcd, mr):
        # units input: [m, m, m, m, N/m^2, N/m^2]
        a_s = np.pi * di ** 2 / (4 * s) * b  # [m^2]
        omega = a_s * fsd / (d * b * fcd) # [-]
        mu = a_s * fsd * d * (1 - omega / 2)  # [Nm]
        x = omega * d / 0.85  # [m]
        if x / d <= 0.35 and mu >= mr:
            return mu, x, a_s, 1
        elif x / d <= 0.5 and mu >= mr:
            return mu, x, a_s, 2
        else:
            return mu, x, a_s, 99  # Querschnitt hat ungenügendes Verformungsvermögen

    @staticmethod
    def mu_unsigned_different_widths(di, s, d, b_as, b_comp, fsd, fcd, mr):
        # Negative bending of ribbed concrete beams: the upper slab
        # reinforcement is active over the effective flange width, while the
        # compression zone is conservatively limited to the rib/web width.
        a_s = np.pi * di ** 2 / (4 * s) * b_as  # [m2]
        omega = a_s * fsd / (d * b_comp * fcd)
        mu = a_s * fsd * d * (1 - omega / 2)
        x = omega * d / 0.85
        if x / d <= 0.35 and mu >= mr:
            return mu, x, a_s, 1
        elif x / d <= 0.5 and mu >= mr:
            return mu, x, a_s, 2
        else:
            return mu, x, a_s, 99

    @staticmethod
    def mu_unsigned_PB(di, n, d, b, h_f, fsd, fcd, mr):
        a_s = np.pi * di ** 2 / 4 * n  # [m^2]
        omega = a_s * fsd / (d * b * fcd)  #[-]
        mu_PB = a_s * fsd * d * (1 - omega / 2)  # [Nm]
        x = omega * d / 0.85
        if x > h_f:
            #print("Druckzonenhöhe > Plattenhöhe")
            mu_PB = 0
            return mu_PB, x, a_s, 99
        else:
            pass

        if x / d <= 0.35 and mu_PB >= mr:
            return mu_PB, x, a_s, 1
        elif x / d <= 0.5 and mu_PB >= mr:
            return mu_PB, x, a_s, 2
        else:
            return mu_PB, x, a_s, 99  # Querschnitt hat ungenügendes Verformungsvermögen

    def calc_shear_resistance(self, bauteil='Platte', d_installation=0.0):
        # calculates shear resistance with d
        di_r = self.bw_bg_r[0]  # diameter
        s_r = self.bw_bg_r[1]  # spacing
        n_r = self.bw_bg_r[2]  # number of stirrups per spacing
        fck = self.concrete_type.fck
        fcd = self.concrete_type.fcd
        tcd = self.concrete_type.tcd
        dmax = self.concrete_type.dmax  # dmax in mm
        fsk = self.rebar_type.fsk
        fsd = self.rebar_type.fsd
        es = self.rebar_type.Es
        bw = self.b
        b_w = self.b_w
        d, d_PB = self.d, self.d_PB
        ds, ds_PB = self.ds, self.ds_PB
        x_p, x_PB_p = self.x_p, self.x_PB_p
        x_n, x_PB_n = self.x_n, self.x_PB_n
        as_bw = 0
        as_PB_bw = np.pi * di_r ** 2 / 4 * n_r / s_r * 0.9 * d_PB

        if bauteil == 'Platte':
            if d_installation < d / 6:  #SIA 262 4.3.3.2.8
                dv_p = d
            else:
                dv_p = d - d_installation
            if d_installation < ds / 6:
                dv_n = ds
            else:
                dv_n = ds - d_installation

            vu_p = self.vu_unsigned(bw, as_bw, d, dv_p, x_p, fck, fcd, tcd, fsk, fsd, es, dmax)
            vu_n = self.vu_unsigned(bw, as_bw, ds, dv_n, x_n, fck, fcd, tcd, fsk, fsd, es, dmax)

            return vu_p, vu_n, as_bw

        else:
            if d_installation < d_PB / 6:  #SIA 262 4.3.3.2.8
                dv_PB_p = d_PB
            else:
                dv_PB_p = d_PB - d_installation
            if d_installation < ds_PB / 6:
                dv_PB_n = ds_PB
            else:
                dv_PB_n = ds_PB - d_installation

            vu_PB_p = self.vu_unsigned(b_w, as_PB_bw, d_PB, dv_PB_p, x_PB_p, fck, fcd, tcd, fsk, fsd, es, dmax)
            vu_PB_n = self.vu_unsigned(b_w, as_PB_bw, ds_PB, dv_PB_n, x_PB_n, fck, fcd, tcd, fsk, fsd, es, dmax)
            return vu_PB_p, vu_PB_n, as_PB_bw

    @staticmethod
    def vu_unsigned(bw, as_bw, d, dv, x, fck, fcd, tcd, fsk, fsd, es, dmax=32, alpha=np.pi / 4, kc=0.55):
        if as_bw == 0:  # cross-section without stirrups
            ev = 1.5 * fsd / es  # SIA 262, 4.3.3.2.2, (39)
            kg = 48 / (16 + dmax)  # SIA 262, 4.3.3.2.1, (37)
            kd = 1 / (1 + ev * d * kg)  # SIA 262, 4.3.3.2.1, (36)
            vrd = kd * tcd * dv  # SIA 262, 4.3.3.2.1, (35)
            return vrd
        else:  # cross-section with vertical stirrups
            z = d - 0.85 * x / 2
            vrds = as_bw * z * fsd  # SIA 262, 4.3.3.4.3, (43)
            vrdc = bw * z * kc * fcd * np.sin(alpha) * np.cos(
                alpha)  # unit of alpha: [rad]    # SIA 262, 4.3.3.4.6, (45)
            rohw = as_bw / bw /(0.9*d)
            rohw_min = 0.001 * (fck * 1e-6 / 30) ** 0.5 * 500 / (fsk * 1e-6)
            if rohw < rohw_min:
                print("minimal reinforcement ratio of stirrups is lower than required according to SIA 262, (110)")
            return min(vrds, vrdc)

    #ÜBERNOMMEN VON RECHTECK-QS, NICHT ANGEPASST
    @staticmethod
    #SIA 262, 4.4.3.2.5: Annahme für den vollständig gerissenen Zustand
    def f_w_ger(roh, rohs, phi, h, d):
        f = (1 - 20 * rohs) / (10 * roh ** 0.7) * (0.75 + 0.1 * phi) * (h / d) ** 3
        return f

    @staticmethod
    def fire_resistance(section):
        # fire resistance of 1-D load-bearing plates according to SIA 262, Tab.16
        c_nom = section.c_nom
        h = section.h
        b = section.b
        if c_nom >= 0.04 and h >= 0.15 and b >= 0.4:
            resistance = 180
        elif c_nom >= 0.03 and h >= 0.12 and b >= 0.3:
            resistance = 120
        elif c_nom >= 0.03 and h >= 0.1 and b >= 0.2:
            resistance = 90
        elif c_nom >= 0.02 and h >= 0.08 and b >= 0.15:
            resistance = 60
        elif c_nom >= 0.02 and h >= 0.06 and b >= 0.1:
            resistance = 30
        else:
            resistance = 0
        return resistance


# .....................................................................................
class SupStrucRibWood(Section):
    def __init__(self, section_type, b, h, a, t2, t3, n, n_inf):
        super().__init__(section_type)
        self.b = b  # rib width [m]
        self.h = h  # rib height [m]
        self.a = a  # spacing between ribs [m]
        self.t2 = t2  # slab height bottom flange [m]
        self.t3 = t3  # slab height top flange [m]
        self.bc_ef = self.calc_bef('comp') + b  # Effective width top flange compression [m]
        self.bt_ef = self.calc_bef('tens') + b  # Effective width bottom flange tension [m]
        self.a_brutt = self.calc_area()
        self.n = n
        self.n_inf = n_inf
        self.z_s = self.calc_center_of_gravity()
        self.iy, self.iy_inf = self.calc_moment_of_inertia()
        self.w = 0.0

    def calc_area(self):
        # in: width b and bw [m], height h and h_f[m]
        # out: area [m2]
        a_brutt = self.b * self.h / self.a + 1 * self.t2 + 1 * self.t3
        return a_brutt

    def calc_bef(self, sign='comp' ):
        # in: width b and bw [m], Abstand Momentennullpunkte l_0 [m]
        # out: effective width b_eff
        l_0 = self.l0
        if sign == 'comp':
            b_ef_schub = 0.1 * l_0
            b_ef_beulen = 20 * self.t3  # falls Fasern rechtwinklig zu Stegen wären, ist Faktor falsch!
            b_ef = min(b_ef_schub, b_ef_beulen, self.a - self.b)
            return b_ef
        else:
            b_ef_schub = 0.1 * l_0
            b_ef = min(b_ef_schub, self.a - self.b)
            return b_ef

    def calc_center_of_gravity(self):
        # in: Geometry effective width b, h, a, t2, b_ef_t, t3, b_ef_c
        # out: center of gravity z_s [m]
        z_s1 = self.t3 + self.h/2
        z_s2 = self.t3+self.h + self.t2/2
        z_s3 = self. t3/2
        z_s = ((self.b * self.h *z_s1 + self.bt_ef * self.t2 * z_s2 + self.bc_ef * self.t3 * z_s3) /
               (self.b * self.h + self.bt_ef * self.t2 + self.bc_ef * self.t3))
        return z_s

    def calc_moment_of_inertia(self):
        # in: Geometry b, h, t2, bt_ef, t3, bc_ef, zs
        # out: moment of inertia I_y [m^4]

        #z=0: Oberkante obere Beplankung
        z_s1 = self.t3 + self.h/2
        z_s2 = self.t3+self.h + self.t2/2
        z_s3 = self. t3/2

        i_1 = self.n[0] * self.b * self.h ** 3 / 12
        as_1 = self.n[0] * self.b * self.h * abs(self.z_s - z_s1) ** 2
        i_2 = self.n[1] * self.bt_ef * self.t2 ** 3 / 12
        as_2 = self.n[1] * self.bt_ef * self.t2 * abs(self.z_s - z_s2) ** 2
        i_3 = self.n[2] * self.bc_ef * self.t3 ** 3 / 12
        as_3 = self.n[2] * self.bc_ef * self.t3 * abs(self.z_s - z_s3) ** 2
        iy = i_1 + as_1 + i_2 + as_2 + i_3 + as_3
        i_1_inf = self.n_inf[0] * self.b * self.h ** 3 / 12
        as_1_inf = self.n_inf[0] * self.b * self.h * abs(self.z_s - z_s1) ** 2
        i_2_inf = self.n_inf[1] * self.bt_ef * self.t2 ** 3 / 12
        as_2_inf = self.n_inf[1] * self.bt_ef * self.t2 * abs(self.z_s - z_s2) ** 2
        i_3_inf = self.n_inf[2] * self.bc_ef * self.t3 ** 3 / 12
        as_3_inf = self.n_inf[2] * self.bc_ef * self.t3 * abs(self.z_s - z_s3) ** 2
        iy_inf = i_1_inf + as_1_inf + i_2_inf + as_2_inf + i_3_inf + as_3_inf
        return iy, iy_inf

    #     #def calc_strength_elast(self, fy, ty):
    #     #def calc_strength_plast(self, fy, ty):

    def calc_weight(self, rib_material, bottom_material, top_material):
        #  out: product-specific timber hollow-core weight per floor area [N/m2]
        return (
            self.b * self.h / self.a * rib_material.specific_weight
            + self.t2 * bottom_material.specific_weight
            + self.t3 * top_material.specific_weight
        )

#................................................................
class RibWood(SupStrucRibWood):
    # defines properties of ribbed timber slab = "Hohlkastendecke" → box beam floor or "Ripendecke" = → joist floor
    def __init__(self, wood_type_1, wood_type_2, wood_type_3, l0, b, h, a, t2, t3, phi_1=0.6, phi_2=0.6, phi_3=0.6,
                 xi=0.02, ei_b=0.0):  # create a rectangular timber object
        section_type = "wd_rib"
        self.wood_type_1 = wood_type_1
        self.wood_type_2 = wood_type_2
        self.wood_type_3 = wood_type_3

        self.phi_1 = phi_1
        self.phi_2 = phi_2
        self.phi_3 = phi_3
        self.phi = phi_1

        self.l0 = l0

        n, n_inf = self.calc_n()
        super().__init__(section_type, b, h, a, t2, t3, n, n_inf)

        mu1_rand_u, mu1_rand_o, mu2_rand_u, mu2_rand_o, mu3_rand_u, mu3_rand_o = self.calc_mu()
        #print("mu1_rand_u, muq_rand_o, mu2_rand_u, mu2_rand_o, mu3_rand_u, mu3_rand_o =", mu1_rand_u, mu1_rand_o, mu2_rand_u, mu2_rand_o, mu3_rand_u, mu3_rand_o)
        mu_el = max(mu1_rand_u, mu1_rand_o, mu2_rand_u, mu2_rand_o, mu3_rand_u, mu3_rand_o)
        self.mu_max, self.mu_min = [mu_el, -mu_el]
        vu_el = self.calc_vu()
        self.vu_p, self.vu_n = vu_el, vu_el

        self.qs_class_n, self.qs_class_p = [3, 3]  # Required cross-section class: 1:=PP, 2:EP, 3:EE
        self.g0k = self.calc_weight(wood_type_1, wood_type_2, wood_type_3)
        self.w = self.g0k
        self.ei1 = self.wood_type_1.Emmean * self.iy  # elastic stiffness [Nm^2], Zeitpunkt t = 0

        self.volume_wood = self.b * self.h / self.a + self.t2 + self.t3
        # Hollow-core acoustic correction assumes glass wool between ribs.
        # RibWood does not receive a database handle, so the material values are
        # kept in sync with the current floor_struc_prop entry for "Glaswolle".
        self.hollow_core_insulation_thickness = self.h
        self.volume_hollow_core_insulation = max((self.a - self.b) * self.hollow_core_insulation_thickness / self.a, 0.0)
        self.hollow_core_insulation_density = 80.0  # kg/m3, Glaswolle
        self.hollow_core_insulation_weight = 800.0  # N/m3, Glaswolle
        self.hollow_core_insulation_gwp = 1.1  # kg CO2-eq/kg, Glaswolle
        self.hollow_core_insulation_cost = 335.0  # CHF/m3, Glaswolle
        self.hollow_core_insulation_construction_time = 0.1  # h/m2, Glaswolle
        self.hollow_core_insulation_gk = (
            self.volume_hollow_core_insulation
            * self.hollow_core_insulation_weight
        )
        # The insulation is acoustic/non-structural. It is exported as an
        # internal floor-build-up mass, but it must not affect structural
        # self-weight, stiffness, or resistance.
        self.co2_wood = ((self.b*self.h * self.wood_type_1.GWP * self.wood_type_1.density)/self.a
                         + self.t2 * self.wood_type_2.GWP * self.wood_type_2.density
                         + self.t3 * self.wood_type_3.GWP * self.wood_type_3.density)
        self.co2_hollow_core_insulation = (
            self.volume_hollow_core_insulation
            * self.hollow_core_insulation_density
            * self.hollow_core_insulation_gwp
        )
        self.cost_wood = self.b * self.h / self.a * self.wood_type_1.cost + self.t2 * self.wood_type_2.cost + self.t3 * self.wood_type_3.cost
        self.cost_hollow_core_insulation = self.volume_hollow_core_insulation * self.hollow_core_insulation_cost
        self.co2 = self.co2_wood + self.co2_hollow_core_insulation # [kg_CO2_eq/m]
        self.cost = self.cost_wood + self.cost_hollow_core_insulation
        self.construction_time_wood = (
            self.b * self.h / self.a * self.wood_type_1.construction_time
            + self.t2 * self.wood_type_2.construction_time
            + self.t3 * self.wood_type_3.construction_time
        )
        self.construction_time_hollow_core_insulation = self.hollow_core_insulation_construction_time
        self.construction_time = self.construction_time_wood + self.construction_time_hollow_core_insulation
        self.ei_b = ei_b  # stiffness perpendicular to direction of span
        self.xi = xi  # damping factor, preset value see: HBT, Page 47 (higher value for some buildups possible)
        self.h_installation = self.h # height available for installation of services. In case of box beam floor, this is the web height. 
    

    def calc_n(self):
        ft0d = 8.5 #C24
        fc0d = 12.4 #C24
        E0mean = 11000 #C24

        factor = 2/3 #Dreischichtplatte 9/9/9 oder 10/10/10

        n1 = self.wood_type_1.Emmean / self.wood_type_1.Emmean          # Wertigkeit Rippe
        n2 = self.wood_type_2.Emmean*factor / self.wood_type_1.Emmean  # Wertigkeit Beplankung unten           #Todo: EMMEAN reduzieren! Stimmt das?
        n3 = self.wood_type_3.Emmean*factor / self.wood_type_1.Emmean  # Wertigkeit Beplankung oben            #Todo: EMMEAN reduzieren!
        n = [n1, n2, n3]
        n1_inf = (self.wood_type_1.Emmean / (1 + self.phi_1)) / (
                self.wood_type_1.Emmean / (1 + self.phi_1))  # Wertigkeit Rippe t=inf
        n2_inf = (self.wood_type_2.Emmean*factor / (1 + self.phi_2)) / (
                self.wood_type_1.Emmean / (1 + self.phi_1))  # Wertigkeit Beplankung unten t=inf    #Todo: EMMEAN reduzieren!
        n3_inf = (self.wood_type_3.Emmean*factor / (1 + self.phi_3)) / (
                self.wood_type_1.Emmean / (1 + self.phi_1))  # Wertigkeit Beplankung oben t=inf     #Todo: EMMEAN reduzieren!
        n_inf = [n1_inf, n2_inf, n3_inf]
        return n, n_inf

    def calc_mu(self):
        #Nachweise nach SIA 5.3.5 Tafelelemente (Biegeelemente)-----PRÜFEN

        fy1 = self.wood_type_1.fmd
        #print("fy1= ", fy1)
        fy2 = 8600000  #self.wood_type_2.fcd      #Festigkeiten für 3S Platten reduzieren
        fy3 = 5900000  #self.wood_type_3.ftd      #Festigkeiten für 3S Platten reduzieren

        mu1_rand_o = min(self.mu_unsigned(fy1, self.iy, (self.z_s - self.t3), self.n[0]),  # z = zs -t3
                       self.mu_unsigned(fy1, self.iy_inf, (self.z_s - self.t3), self.n_inf[0]))
        mu1_rand_u = min(self.mu_unsigned(fy1, self.iy, (self.h + self.t3 - self.z_s), self.n[0]),  # z = h + t3 -zs
                       self.mu_unsigned(fy1, self.iy_inf,(self.h + self.t3 - self.z_s), self.n_inf[0]))


        mu2_rand_o = min(self.mu_unsigned(fy2, self.iy, (self.t3 + self.h - self.z_s ), self.n[1]),  # z = t3 + h - zs
                         self.mu_unsigned(fy2, self.iy_inf, (self.t3 + self.h - self.z_s ), self.n_inf[1]))
        mu2_rand_u = min(self.mu_unsigned(fy2, self.iy, (self.t3 + self.h + self.t2- self.z_s ), self.n[1]),  # z = t3 + h + t2 - zs
                         self.mu_unsigned(fy2, self.iy_inf, (self.t3 + self.h + self.t2- self.z_s ), self.n_inf[1]))

        mu3_rand_o = min(self.mu_unsigned(fy3, self.iy, self.z_s, self.n[2]),  # z = zs
                         self.mu_unsigned(fy3, self.iy_inf, self.z_s, self.n_inf[2]))
        mu3_rand_u = min(self.mu_unsigned(fy3, self.iy, (self.z_s - self.t3), self.n[2]),  # z = zs -t3
                         self.mu_unsigned(fy3, self.iy_inf, (self.z_s - self.t3), self.n_inf[2]))
        return mu1_rand_u, mu1_rand_o, mu2_rand_u, mu2_rand_o, mu3_rand_u, mu3_rand_o

    @staticmethod
    def mu_unsigned(fy, iy, z, n):
        mu = fy * iy / z / n
        return mu

    def calc_vu(self):
        ty1 = self.wood_type_1.fvd
        vu_1 = ty1 * self.b * self.h / 1.5  #nur Rippe angesetzt
        return vu_1

    # FEHLT: Rollschubnachweis!!


#TODO: Aktueller Stand wird kein Abbrand des Hohlkastenquerschnitts berechnet, die Schichtdicken werden gem. Lignum so gewählt, dass der Abbrand nicht Bemessen werden muss.
#TODO: Folgende Zeilen müssen angepasst werden, wenn ein anderes Prinzip gewählt wird.
    @staticmethod
    def fire_resistance(section):
         #bnds = [(0, 240)]
         #t0 = 60
         #max_t = minimize(RectangularWood.fire_minimizer, t0, args=[member], bounds=bnds)
         #t_max = max_t.x[0]
        t2 = section.t2
        t3 = section.t3
        b = section.b
        h = section.h
        if t2 >= 50: #and b > ? and h > ? and t3 >= ?
            resistance = 90
        if t2 >= 26 and b > 60 and h > 180 and t3 >= 27:
            resistance = 60
        if t2 >= 10: #and b > ? and h > ? and t3 >= ?
            resistance = 30
        else:
            resistance = 0
        return resistance

    # @staticmethod
    # def fire_minimizer(t, args):
    #     member = args[0]
    #     rem_sec = RectangularWood.remaining_section(member.section, member.fire, t)
    #     mu_fire = 1.8 * rem_sec.mu_max
    #     vu_fire = 1.8 * rem_sec.vu_p  # SIA 265 (51)
    #     qd_fire = member.psi[2] * member.qk + member.gk
    #     qd_fire_zul = min(mu_fire / (max(member.system.alpha_m) * member.system.l_tot ** 2),
    #                           vu_fire / (max(member.system.alpha_v) * member.system.l_tot))
    #     to_opt = abs(qd_fire - qd_fire_zul)
    #     return to_opt
    #
    #     staticmethod
    # def remaining_section(section, fire, t=60, dred=0.007):
    #     betan = section.wood_type.burn_rate
    #     dcharn = betan * t
    #     d_ef = dcharn + dred
    #     h_fire = max(section.h - d_ef * (fire[0] + fire[2]))
    #     b_fire = max(section.b - d_ef * (fire[1] + fire[3]), 0)
    #     rem_sec = RectangularWood(section.wood_type, b_fire, h_fire)
    #     return rem_sec

# ........................................................................
class SupStrucTCC(Section): #takes the geometric parameters of the TCC cross-section as input parameters and calculates the geometric cross-sectional values
    def __init__(self, section_type, a_ribs, h_c, h_w, b_w, d, l0):
        super().__init__(section_type)
        self.a_ribs = a_ribs  # spacing of timber beams [m]  
        self.h_c = h_c  # height of concrete layer [m]
        self.h_w = h_w  # height of timber beams [m]
        self.h = h_c + h_w + d  # total height of cross section
        self.b_w = b_w  # width of timber beams [m]
        self.d = d  # thickness of formwork [m]
        self.l0 = l0  # distance between moment zero points [m]
        self.b_ceff = self.calc_beff(a_ribs, b_w, l0)  # effective width of concrete layer [m]
        self.A_w = self.calc_area(h_w, b_w)  # area of timber beam [m^2]
        self.A_c = self.calc_area(h_c, self.b_ceff)  # area of concrete layer according to effective width [m^2]
        self.I_yw = self.calc_moment_of_inertia(h_w, b_w)  # moment of inertia of timber beam [m^4]
        self.I_yc = self.calc_moment_of_inertia(h_c, self.b_ceff)  # moment of inertia of concrete layer according to effective width [m^4]
        self.w = 0.0

    def calc_beff(self, a_ribs, b_w, l0):
        # in: spacing of timber beams [m], width of timber beams [m]
        # out: effective width of concrete layer according to SIA 262 [m]
        b_effi = min(0.2*(a_ribs-b_w)/2+0.1*l0, 0.2*l0) 
        b_ceff = min(2*b_effi + b_w, a_ribs)
        return b_ceff
    
    def calc_area(self, h, b):
        # in: height of layer [m], width of layer [m]
        # out: area of layer [m^2]
        A = h * b
        return A
    
    def calc_moment_of_inertia(self, h, b):
        # in: height of layer [m], width of layer [m]
        # out: moment of inertia of layer [m^4]
        I_y = b * h**3 / 12
        return I_y
    
    def calc_weight(self, wood_material, concrete_material, rebar_material=None, wood_volume=None,
                    concrete_volume=None, reinforcement_volume=0.0):
        # out: product-specific TCC weight per floor area [N/m2]
        wood_volume = self.A_w / self.a_ribs if wood_volume is None else max(wood_volume, 0.0)
        concrete_volume = self.h_c if concrete_volume is None else max(concrete_volume, 0.0)
        rebar_weight = 0.0
        if rebar_material is not None:
            rebar_weight = rebar_material.specific_weight * max(reinforcement_volume, 0.0)
        return (
            wood_material.specific_weight * wood_volume
            + concrete_material.specific_weight * concrete_volume
            + rebar_weight
        )
    
class TCC(SupStrucTCC):
    def __init__(self, concrete_type, rebar_type, wood_type, connector_type, s, a_ribs, h_c, h_w, b_w, d, l0, xi=0.02, ):
        section_type = "tcc"
        super().__init__(section_type, a_ribs, h_c, h_w, b_w, d, l0)
        self.concrete_type = concrete_type
        self.rebar_type = rebar_type
        self.wood_type = wood_type
        self.connector_type = connector_type
        self.qs_class_n, self.qs_class_p = [3, 3] 

        self.s = s  # spacing of connectors [m]
        self.gamma_ULS, self.gamma_SLS, self.psi_ULS, self.psi_SLS = self.calc_gamma()
        self.EI_ULS, self.EI_SLS, self.a_ULS, self.a_SLS = self.calc_EIeff()
        self.Mu = self.calc_mu() #Nm/m'
        self.Vu = self.calc_vu() #N/m'

        self.rebar_d = 0.006
        self.rebar_s = 0.150
        # One central reinforcement mesh: two orthogonal bar directions.
        self.rebar_layers = 2
        self.as_rebar = self.calc_tcc_rebar_area(self.rebar_d, self.rebar_s, self.rebar_layers)
        wood_volume = self.d + self.A_w / self.a_ribs
        concrete_volume = max(self.h_c - self.as_rebar, 0.0)
        connector_gwp = getattr(self.connector_type, "GWP", 0.0) / (self.s * self.a_ribs)
        self.volume_wood = wood_volume
        self.volume_concrete = concrete_volume
        self.volume_reinforcement = self.as_rebar
        self.co2_wood = wood_volume * self.wood_type.GWP * self.wood_type.density
        self.co2_concrete = concrete_volume * self.concrete_type.GWP * self.concrete_type.density
        self.co2_rebar = self.as_rebar * self.rebar_type.GWP * self.rebar_type.density
        self.co2_connector = connector_gwp
        self.cost_wood = wood_volume * self.wood_type.cost
        self.cost_concrete = concrete_volume * self.concrete_type.cost
        self.cost_rebar = self.as_rebar * self.rebar_type.cost
        self.cost_connector = self.connector_type.cost / (self.s * self.a_ribs)
        self.co2 = self.co2_wood + self.co2_concrete + self.co2_rebar + self.co2_connector  # [kg_CO2_eq/m2]
        self.cost = self.cost_connector + self.cost_wood + self.cost_concrete + self.cost_rebar  # [CHF/m2]
        self.construction_time = (self.connector_type.construction_time / (self.s * self.a_ribs)
                                  + wood_volume * self.wood_type.construction_time
                                  + concrete_volume * self.concrete_type.construction_time
                                  + self.as_rebar * self.rebar_type.construction_time)  # [h/m2]
        self.g0k = self.calc_weight(
            self.wood_type,
            self.concrete_type,
            self.rebar_type,
            wood_volume,
            concrete_volume,
            self.as_rebar,
        )
        self.w = self.g0k
        self.ei1 = self.EI_SLS[0]  # elastic stiffness at t=0 for SLS checks
        self.xi = xi
        self.ei_b = self.concrete_type.Ecm * self.h_c**3 / 12  # stiffness perpendicular to direction of span per m witdh
        self.phi = 1 #dummy that is not used, but needed that nothing crashes
        # Positive capacities (dummy values)
        self.mu_max = 1
        self.vu_p = 1
    
        # Negative capacities (Never used, just here to prevent crashes)
        self.mu_min = 0.0
        self.vu_n = 0.0

        self.h_installation = self.get_h_installation() # height available for installation of services. In case of box beam floor, this is the web height.
        # Define string as plot label that names connector type and fixed geometric parameters of TCC for plotting purposes
        #self.plot_label = f"TCC: {connector_type.name}, b_w={b_w}m, a_ribs={a_ribs}, s={s}m, d={d}m"
    @staticmethod
    def calc_tcc_rebar_area(di=0.010, spacing=0.150, n_layers=2):
        return n_layers * np.pi * di ** 2 / 4 / spacing

    def get_h_installation(self):
        if self.b_w == self.a_ribs: #Solid slab
            return max(self.h_c - 0.04*2,0)
        else: #Ribbed slab
            return self.h_w
    
    def calc_gamma(self):
        # Initialize array for gamma values at different time points
        gamma_ULS = np.zeros(2) #gamma_ULS[0] for t=0, gamma_ULS[1] for t=inf
        gamma_SLS = np.zeros(2) #gamma_SLS[0] for t=0, gamma_SLS[1] for t=inf

        # Initialize 2x3 array for psi values at different time points for concrete, wood, and connector for ULS
        psi_ULS = np.zeros((2, 3)) # Rows: 0 for t=0, 1 for t=inf; Columns: 0 for concrete, 1 for wood, 2 for connector
        # Initialize 2x3 array for psi values at different time points for concrete, wood, and connector for SLS
        psi_SLS = np.zeros((2, 3)) # Rows: 0 for t=0, 1 for t=inf; Columns: 0 for concrete, 1 for wood, 2 for connector

        # All psi at t=0 are 1
        psi_ULS[0, :] = 0
        psi_SLS[0, :] = 0

        # t_0
        gamma_ULS[0] = 1 / (1 + np.pi**2 * self.concrete_type.Ecm * self.A_c * self.s / (self.connector_type.K_ser * 2/3 * self.l0**2))
        gamma_SLS[0] = 1 / (1 + np.pi**2 * self.concrete_type.Ecm * self.A_c * self.s / (self.connector_type.K_ser * self.l0**2))

        # Precompute common terms for interpolation
        phi_diff = self.concrete_type.phi - 2.5
        phi_ratio = (self.wood_type.phi - 0.6) / 0.2

        # ULS
        # psi t=inf
        psi_conc_ULSinf_06 = 2.6 - 0.8 * gamma_ULS[0]**2 + (2.0 - 0.5 * gamma_ULS[0]**1.9 - (2.6 - 0.8 * gamma_ULS[0]**2)) * phi_diff
        psi_conc_ULSinf_08 = 2.3 - 0.5 * gamma_ULS[0]**2.6 + (1.8 - 0.3 * gamma_ULS[0]**2.5 - (2.3 - 0.5 * gamma_ULS[0]**2.6)) * phi_diff
        psi_ULS[1, 0] = psi_conc_ULSinf_06 + (psi_conc_ULSinf_08 - psi_conc_ULSinf_06) * phi_ratio # psi t=inf for concrete
        psi_ULS[1, 1] = psi_ULS[1, 2] = 1 # psi t=inf for wood and connector
        # Calculate gamma ULS at t=inf
        E_c_ULSinf = self.concrete_type.Ecm / (1 + psi_ULS[1, 0] * self.concrete_type.phi)
        K_ULSinf = self.connector_type.K_ser * 2/3 / (1 + psi_ULS[1, 2] * self.wood_type.phi * 2)
        gamma_ULS[1] = 1 / (1 + np.pi**2 * E_c_ULSinf * self.A_c * self.s / (K_ULSinf * self.l0**2)) # gamma ULS at t=inf

        # SLS
        # psi t=inf
        psi_conc_SLSinf_06 = 2.6 - 0.8 * gamma_SLS[0]**2 + (2.0 - 0.5 * gamma_SLS[0]**1.9 - (2.6 - 0.8 * gamma_SLS[0]**2)) * phi_diff
        psi_conc_SLSinf_08 = 2.3 - 0.5 * gamma_SLS[0]**2.6 + (1.8 - 0.3 * gamma_SLS[0]**2.5 - (2.3 - 0.5 * gamma_SLS[0]**2.6)) * phi_diff
        psi_SLS[1, 0] = psi_conc_SLSinf_06 + (psi_conc_SLSinf_08 - psi_conc_SLSinf_06) * phi_ratio # psi t=inf for concrete
        psi_SLS[1, 1] = psi_SLS[1, 2] = 1 # psi t=inf for wood and connector
        # Calculate gamma SLS at t=inf
        E_c_SLSinf = self.concrete_type.Ecm / (1 + psi_SLS[1, 0] * self.concrete_type.phi)
        K_SLSinf = self.connector_type.K_ser / (1 + psi_SLS[1, 2] * self.wood_type.phi * 2)
        gamma_SLS[1] = 1 / (1 + np.pi**2 * E_c_SLSinf * self.A_c * self.s / (K_SLSinf * self.l0**2)) # gamma SLS at t=inf

        #gamma must be between 0...1
        gamma_ULS = np.clip(gamma_ULS, 0.0001, 1)
        gamma_SLS = np.clip(gamma_SLS, 0.0001, 1)

        return gamma_ULS, gamma_SLS, psi_ULS, psi_SLS
    
    
    def calc_EIeff(self):
        # Initialize arrays for effective stiffness at ULS and SLS
        EI_ULS = np.zeros(2) #EI_ULS[0] for t=0, EI_ULS[1] for t=inf
        EI_SLS = np.zeros(2) #EI_SLS[0] for t=0, EI_SLS[1] for t=inf
        # Initialize 2x2 array for a_i values at ULS and SLS
        a_ULS = np.zeros((2, 2)) #Rows for t=0, t=inf, Columns for concrete and wood 
        a_SLS = np.zeros((2, 2)) #Rows for t=0, t=inf, Columns for concrete and wood 

        # Calculate a_i values for ULS at different time points i
        for i in range(2):  # Only t=0 and t=inf
            Ec = self.concrete_type.Ecm/(1+self.psi_ULS[i,0]*self.concrete_type.phi)
            Ew = self.wood_type.Emmean/(1+self.psi_ULS[i,1]*self.wood_type.phi)
            a_ULS[i, 1] = (self.gamma_ULS[i] * Ec * self.A_c*((self.h_c+self.h_w)/2+self.d)) / ((self.gamma_ULS[i] * Ec * self.A_c + Ew * self.A_w)) #a_wood at ULS
            a_ULS[i, 0] = ((self.h_c+self.h_w)/2 + self.d) - a_ULS[i,1] #a_concrete at ULS

        # Calculate a_i values for SLS at different time points
        for i in range(2):  # Only t=0 and t=inf 
            Ec = self.concrete_type.Ecm/(1+self.psi_SLS[i,0]*self.concrete_type.phi)
            Ew = self.wood_type.Emmean/(1+self.psi_SLS[i,1]*self.wood_type.phi)
            a_SLS[i, 1] = (self.gamma_SLS[i] * Ec * self.A_c*((self.h_c+self.h_w)/2+self.d)) / ((self.gamma_SLS[i] * Ec * self.A_c + Ew * self.A_w)) #a_wood at SLS
            a_SLS[i, 0] = ((self.h_c+self.h_w)/2 + self.d) - a_SLS[i,1] #a_concrete at SLS

        # Calculate effective stiffness at ULS for different time points
        for i in range(2):  # Only t=0 and t=inf
            Ec = self.concrete_type.Ecm/(1+self.psi_ULS[i,0]*self.concrete_type.phi)
            Ew = self.wood_type.Emmean/(1+self.psi_ULS[i,1]*self.wood_type.phi)
            EI_ULS[i] += Ec*(self.I_yc + self.gamma_ULS[i]*self.A_c*a_ULS[i,0]**2)/self.a_ribs #divide by a_ribs to get per m of total width
            EI_ULS[i] += Ew*(self.I_yw + self.A_w*a_ULS[i,1]**2)/self.a_ribs #divide by a_ribs to get per m of total width

        # Calculate effective stiffness at SLS for different time points
        for i in range(2):  # Only t=0 and t=inf
            Ec = self.concrete_type.Ecm/(1+self.psi_SLS[i,0]*self.concrete_type.phi)
            Ew = self.wood_type.Emmean/(1+self.psi_SLS[i,1]*self.wood_type.phi)
            EI_SLS[i] += Ec*(self.I_yc + self.gamma_SLS[i]*self.A_c*a_SLS[i,0]**2)/self.a_ribs #divide by a_ribs to get per m of total width
            EI_SLS[i] += Ew*(self.I_yw + self.A_w*a_SLS[i,1]**2)/self.a_ribs #divide by a_ribs to get per m of total width
        
        return EI_ULS, EI_SLS, a_ULS, a_SLS
    
    def calc_mu(self):
        # Field momentresistance
        # Initialize array for m_u at different time points
        mu = np.zeros(2) #mu[0] for t=0, mu[1] for t=inf

        # Get material properties for concrete at design level ULS
        fcd = self.concrete_type.fcd

        # Get material properties for wood at design level ULS
        fmd = self.wood_type.fmd

        # k_mod to account for wood stiffness reduction due to load duration EN1995-1-1 (same as eta_t in SIA 265)
        k_mod = 1

        # Calculate m_u at ULS for t=0, t=inf in [Nm/m']
        for i in range(2): 
            if i == 1: #t=inf, apply k_mod for wood stiffness reduction
                k_mod = 0.6 # for load duration class 3 (long-term load) according to EN1995-1-1, Table 3.1
            mu[i] = min(fcd * self.EI_ULS[i] / (self.concrete_type.Ecm/(1+self.psi_ULS[i,0]*self.concrete_type.phi))*1/(self.gamma_ULS[i]*self.a_ULS[i,0]+self.h_c/2), #concrete edge stress in Nm/m'
                        fmd * k_mod * self.EI_ULS[i] / (self.wood_type.Emmean/(1+self.psi_ULS[i,1]*self.wood_type.phi))*1/(self.a_ULS[i,1]+self.h_w/2)) #Nm/m'
            
        # Calculate m_u of the concrete cross section alone for t=0
        # Find minimal reinforcement
        A_s = 0.002*self.b_ceff*self.h_c/2 #minimal reinforcement area lower reinforcement
        d = self.h_c-2e-2-0.5e-2 #effective depth of reinforcement, assume 2cm concrete cover and 1cm rebar diameter
        m_cmin = A_s * self.rebar_type.fsd * (d - A_s * self.rebar_type.fsd / (2 * self.b_ceff * fcd))
        mr = self.b_ceff * self.h_c ** 2 / 6 * 1.3 * self.concrete_type.fctm  #cracking moment

        mu[0] = max(mu[0], max(m_cmin/self.a_ribs, mr/self.a_ribs)) #ensure that the moment resistance is at least as high as the cracking moment and the moment resistance of the minimal reinforced concrete section, divide by a_ribs to get per m of total width
        
        return mu
    
    def calc_vu(self):
        # Shear resistance
        # Initialize array for v_u at different time points
        vu = np.zeros(2) #vu[0] for t=0, vu[1] for t=inf

        # Get material properties for wood at design level ULS
        fvd = self.wood_type.fvd

        # k_mod to account for wood stiffness reduction due to load duration EN1995-1-1 (same as eta_t in SIA 265)
        k_mod = 1

        # Calculate m_u at ULS for t=0, t=inf in [N/m']
        for i in range(2): 
            if i == 1: #t=inf, apply k_mod for wood stiffness reduction
                k_mod = 0.6 # for load duration class 3 (long-term load) according to EN1995-1-1, Table 3.1
            vu[i] = (2*fvd * k_mod * self.EI_ULS[i] / (self.wood_type.Emmean/(1+self.psi_ULS[i,1]*self.wood_type.phi))*1/(self.a_ULS[i,1]+self.h_w/2)**2) #N/m'

        return vu
    
    @staticmethod
    def fire_resistance(member):
        t_max_limit = 60.0
        
        # Check interval endpoints first
        diff_0 = TCC.fire_minimizer(0.0, member)
        if diff_0 < 0:
            return 0.0 # member fails even at t=0, so fire resistance is 0 minutes
        diff_max = TCC.fire_minimizer(t_max_limit, member)
        if diff_max > 0:
            return t_max_limit #member still safe at t=240, so fire resistance is at least 240 minutes
            
        # Find the root between 0 and t_max_limit 
        try:
            sol = root_scalar(TCC.fire_minimizer, args=(member,), bracket=[0.0, t_max_limit],  method='brentq')
            if sol.converged:
                return sol.root
            else:
                return 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def fire_minimizer(t, member):
        
        if isinstance(t, (list, np.ndarray)):
            t_val = float(t[0])
        else:
            t_val = float(t)
            
        rem_sec = TCC.remaining_section(member.section, member.fire, t_val)
        
        if rem_sec is None:
            return -qd_fire 
            
        mu_fire = 1.8 * rem_sec.Mu[0] # SIA 265 (51)
        vu_fire = 1.8 * rem_sec.Vu[0] # SIA 265 (51)
        
        qd_fire = member.psi[2] * member.qk + member.gk
        
        qd_fire_zul = min(mu_fire / (max(member.system.alpha_m) * member.system.l_tot ** 2),
                          vu_fire / (max(member.system.alpha_v) * member.system.l_tot))     
        return qd_fire_zul - qd_fire #return t_opt

    @staticmethod
    def remaining_section(section, fire, t, dred=0.007):
        # Fire is a list of integers: [bottom, left, top, right] 1: means exposed to fire, 0 means not exposed to fire.
        # For TCC ribbed, [1,1,0,1] 
        # For TCC slab, [1,0,0,0] 
    
        # Wood charring rate (beta_n)
        dcharn = section.wood_type.burn_rate #  m/min for compatibility with other dimensions in m
        if t > 0:
            d_ef = dcharn * t + dred # Effective charring depth m
        else:
            d_ef = 0

        # Reduce timber rib width (usually exposed on left and right)
        b_w_red = section.b_w
        b_w_red -= d_ef*fire[1]  # Left side
        b_w_red -= d_ef*fire[3]  # Right side

        # Reduce timber rib height (exposed from bottom)
        h_w_red = section.h_w
        h_w_red -= d_ef*fire[0]  # Bottom
        
        # Wood has completely burned away
        # CS has to be limited, otherwise Gamma calculation will crash
        if b_w_red <= 0 or h_w_red <= 0:
            b_w_red = 0.06 # Prevent division by zero errors
            h_w_red = 0.08 # Prevent division by zero errors

        # Reduce the connector stiffness if screws are used as connectors
        k_modFi = 1 # Modification factor for connector stiffness according to Lignum 3.1, Table 46-1
        if section.connector_type.name != "kerve":
            a = (b_w_red - 0.03)/2 #Assume connectors use 3cm of timber width (A46-1) Lignum 3.1
            a_mm = a * 1000 # convert to mm to correctly use the formula from Lignum 3.1, Table 46-1
            if a_mm<=0.6*t: k_modFi = 0.0001 #prevent division by zero 
            elif a_mm<=0.8*t+3: k_modFi = (0.2*a_mm-0.12*t)/(0.2*t+3)
            elif a_mm<= t+24: k_modFi = (a_mm*0.8-0.6*t+1.8)/(0.2*t+21)
            else: k_modFi = 1
        
        try:
            # reduced connector stiffness
            reduced_connector = copy.deepcopy(section.connector_type)
            reduced_connector.K_ser = float(reduced_connector.K_ser) * k_modFi
            
            # Return remaining section
            return TCC(section.concrete_type, section.rebar_type, section.wood_type, 
                       reduced_connector, section.s, section.a_ribs, section.h_c, 
                       h_w_red, b_w_red, section.d, section.l0)
        
        except Exception as e:
            # gamma calculation crashes as section becomes to small 
            return None
    
    
       


#-----------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------
class MatLayer:  # create a material layer
    def __init__(self, mat_name, h_input, roh_input, database):  # get initial data from database
        self.name = mat_name
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        # get properties from database
        inquiry = ("""SELECT "h_fix [float, m]", "E [float, N/m^2]", "density [float, kg/m^3]", "weight [float, N/m^3]",
         "GWP [float, kg/kg]", "Cost [float, CHF/m3]", "T_construction [h/m2]" FROM floor_struc_prop WHERE "name[string]"=""" + mat_name)
        cursor.execute(inquiry)
        result = cursor.fetchall()
        h_fix, e, density, weight, self.GWP, cost, self.construction_time = result[0]
        if h_input is False:
            if h_fix is None:
                raise ValueError(f"Layer {mat_name} requires a fixed height in floor_struc_prop when h_input is False.")
            self.h = h_fix
        else:
            self.h = h_input
        if roh_input is False:
            self.density = density
            self.weight = weight
        else:
            self.density = roh_input
            self.weight = roh_input * 10
        if e == None:
            self.ei = 0.0
        else:
            i = 1 * self.h ** 3 / 12
            self.ei = e * i
        self.gk = self.weight * self.h  # weight per area in N/m^2
        self.co2 = self.density * self.h * self.GWP  # CO2-eq per area in kg-C02/m^2
        self.cost = self.h * cost  # cost per area in CHF/m^2


class FloorStruc:  # create a floor structure
    def __init__(self, mat_layers, database_name):
        self.layer_specs = list(mat_layers)
        self.database_name = database_name
        self.layers = []
        self.co2 = 0
        self.cost = 0 #CHF/m^2
        self.construction_time = 0 #h/m^2
        self.gk_area = 0
        self.h = 0
        self.ei = 0
        for mat_name, h_input, roh_input in mat_layers:
            current_layer = MatLayer(mat_name, h_input, roh_input, database_name)
            self.layers.append(current_layer)
            self.co2 += current_layer.co2
            self.cost += current_layer.cost
            self.construction_time += current_layer.construction_time
            self.gk_area += current_layer.gk
            self.h += current_layer.h
            self.ei = max(self.ei, current_layer.ei)





class AcousticResult:
    def __init__(self, floorstruc, rw, lnw, gravel_thickness, screed_thickness,
                 delta_gravel, delta_hollow_core, delta_rw_floating, delta_lnw_floating,
                 f0_airborne=None, f0_impact=None, delta_tcc_topping=0.0,
                 model_branch="standard", validity_warnings=None):
        self.floorstruc = floorstruc
        self.rw = rw
        self.lnw = lnw
        self.gravel_thickness = gravel_thickness
        self.screed_thickness = screed_thickness
        self.delta_gravel = delta_gravel
        self.delta_hollow_core = delta_hollow_core
        self.delta_rw_floating = delta_rw_floating
        self.delta_lnw_floating = delta_lnw_floating
        self.f0_airborne = f0_airborne
        self.f0_impact = f0_impact
        self.delta_tcc_topping = delta_tcc_topping
        self.model_branch = model_branch
        self.validity_warnings = validity_warnings or []


class AcousticFloorGenerator:
    parquet = "'Parkett 2-Schicht werkversiegelt, 11 mm'"
    glass_wool = "'Glaswolle'"
    cement_screed = "'Unterlagsboden Zement, 85 mm'"
    gravel = "'Kies gebrochen'"

    @staticmethod
    def section_mass(section):
        return section.w / 10 # convert from N/m^2 to kg/m^2

    @staticmethod
    def planning_surcharge(section):
        if section.section_type in ("rc_rec", "pc_rec", "rc_rib", "tcc"):
            return 5.0
        if section.section_type in ("wd_rec", "wd_rib"):
            return 8.0
        return 0.0

    @staticmethod
    def target_values(section, requirements):
        surcharge = AcousticFloorGenerator.planning_surcharge(section)
        return requirements.rw_min + surcharge, requirements.lnw_max - surcharge

    @staticmethod
    def hollow_core_damping(section):
        h_ins = section.hollow_core_insulation_thickness if isinstance(section, RibWood) else 0.0
        return min(6 * h_ins / 0.20, 7.0)

    @staticmethod
    def gravel_damping(m_gravel, m_section):
        if m_gravel <= 0:
            return 0.0
        return min(min(max(m_gravel / m_section, 1), 2) * m_gravel / 40, 6)

    @staticmethod
    def is_tcc(section):
        return getattr(section, "section_type", None) == "tcc"

    @staticmethod
    def tcc_concrete_topping_mass(section):
        if not AcousticFloorGenerator.is_tcc(section):
            return 0.0
        if hasattr(section, "acoustic_concrete_topping_mass"):
            return max(float(section.acoustic_concrete_topping_mass), 0.0)
        concrete = getattr(section, "concrete_type", None)
        density = getattr(concrete, "density", 2500.0)
        h_c = getattr(section, "h_c", 0.0)
        return max(float(density) * float(h_c), 0.0)

    @staticmethod
    def effective_spring_stiffness(section, floorstruc, spring_stiffness):
        """Return the dynamic stiffness of insulation layers acting in series."""
        if not AcousticFloorGenerator.is_tcc(section):
            return spring_stiffness

        insulation_layers = [
            layer for layer in floorstruc.layers
            if layer.name == AcousticFloorGenerator.glass_wool
        ]
        if len(insulation_layers) <= 1:
            return spring_stiffness

        # The TCC acoustic build-up uses two glass-wool layers (see lignumdata HBV floor build-ups)
        # For equal insulation mats in series: 1 / s_eff = sum(1 / s_i).
        return 1 / sum(1 / spring_stiffness for _ in insulation_layers)

    @staticmethod
    def floating_screed_improvement(m_base, m_screed, spring_stiffness, rw_mass, impact_band_max=5000):
        f0_airborne = 1 / (2 * np.pi) * np.sqrt(spring_stiffness * 1e6 * (1 / m_base + 1 / m_screed))
        delta_rw_floating = 74.4 - 20 * np.log10(f0_airborne) - rw_mass / 2

        f0_impact = 160 * np.sqrt(spring_stiffness / m_screed)
        band_frequencies = np.array([50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000,
                                     1250, 1600, 2000, 2500, 3150, 4000, 5000])
        band_frequencies = band_frequencies[band_frequencies <= impact_band_max]
        delta_lnw_floating = np.average(30 * np.log10(band_frequencies / f0_impact))
        return delta_rw_floating, delta_lnw_floating, f0_airborne, f0_impact

    @staticmethod
    def acoustic_validity_warnings(section, f0_airborne, f0_impact):
        warnings = []
        if AcousticFloorGenerator.is_tcc(section):
            for label, f0 in (("airborne", f0_airborne), ("impact", f0_impact)):
                if f0 is None:
                    continue
                if f0 > 100:
                    warnings.append(f"TCC {label} resonance f0={f0:.1f} Hz > 100 Hz; avoid this range.")
                elif f0 > 70:
                    warnings.append(f"TCC {label} resonance f0={f0:.1f} Hz outside preferred 30-70 Hz range.")
                elif f0 < 30:
                    warnings.append(f"TCC {label} resonance f0={f0:.1f} Hz below preferred 30-70 Hz range.")
        return warnings

    @staticmethod
    def evaluate(section, database_name, layer_specs, screed_thickness=0.0,
                 gravel_thickness=0.0, spring_stiffness=6.0):
        floorstruc = FloorStruc(layer_specs, database_name)
        return AcousticFloorGenerator.evaluate_floorstruc(section, floorstruc, spring_stiffness)

    @staticmethod
    def evaluate_floorstruc(section, floorstruc, spring_stiffness=6.0):
        m_section = AcousticFloorGenerator.section_mass(section)
        gravel_layers = [layer for layer in floorstruc.layers if layer.name == AcousticFloorGenerator.gravel]
        m_gravel = sum(layer.density * layer.h for layer in gravel_layers)
        m_tcc_topping = AcousticFloorGenerator.tcc_concrete_topping_mass(section)
        m_base = m_section + m_gravel

        rw_mass = 37.5 * np.log10(m_base) - 42
        lnw_mass = 164 - 35 * np.log10(m_base)

        delta_rw_floating = 0.0
        delta_lnw_floating = 0.0
        f0_airborne = None
        f0_impact = None
        screed_layers = [layer for layer in floorstruc.layers if layer.name == AcousticFloorGenerator.cement_screed]
        screed_thickness = sum(layer.h for layer in screed_layers)
        if screed_thickness > 0:
            m_screed = sum(layer.density * layer.h for layer in screed_layers)
            effective_spring_stiffness = AcousticFloorGenerator.effective_spring_stiffness(
                section, floorstruc, spring_stiffness
            )
            # HBV/TCC floors are governed by low-frequency impact behavior. Using only
            # the low-frequency part keeps the simplified model conservative.
            impact_band_max = 500 if AcousticFloorGenerator.is_tcc(section) else 5000
            delta_rw_floating, delta_lnw_floating, f0_airborne, f0_impact = (
                AcousticFloorGenerator.floating_screed_improvement(
                    m_base, m_screed, effective_spring_stiffness, rw_mass, impact_band_max
                )
            )

        delta_gravel = AcousticFloorGenerator.gravel_damping(m_gravel, m_section)
        m_tcc_timber = max(m_section - m_tcc_topping, 1e-9)
        delta_tcc_topping = AcousticFloorGenerator.gravel_damping(m_tcc_topping, m_tcc_timber)
        delta_hollow_core = AcousticFloorGenerator.hollow_core_damping(section)
        rw = rw_mass + delta_rw_floating + delta_gravel + delta_hollow_core
        lnw = lnw_mass - delta_lnw_floating - delta_gravel - delta_tcc_topping - delta_hollow_core
        gravel_thickness = sum(layer.h for layer in gravel_layers)
        model_branch = "tcc" if AcousticFloorGenerator.is_tcc(section) else "standard"
        validity_warnings = AcousticFloorGenerator.acoustic_validity_warnings(section, f0_airborne, f0_impact)
        return AcousticResult(floorstruc, rw, lnw, gravel_thickness, screed_thickness,
                              delta_gravel, delta_hollow_core, delta_rw_floating, delta_lnw_floating,
                              f0_airborne, f0_impact, delta_tcc_topping, model_branch, validity_warnings)

    @staticmethod
    def generate(section, database_name, requirements=None, gravel_step=0.01, gravel_max=0.30):
        requirements = requirements or AcousticRequirements()
        rw_target, lnw_target = AcousticFloorGenerator.target_values(section, requirements)
        base_layers = [[AcousticFloorGenerator.parquet, False, False]]
        insulation_layers = [[AcousticFloorGenerator.glass_wool, False, False]]
        if AcousticFloorGenerator.is_tcc(section):
            # TCC floors receive two insulation layers. Their dynamic stiffness
            # is evaluated as springs in series in evaluate_floorstruc().
            insulation_layers = [
                [AcousticFloorGenerator.glass_wool, False, False],
                [AcousticFloorGenerator.glass_wool, False, False],
            ]
        candidates = [
            (0.0, base_layers),
            (0.06, base_layers + insulation_layers + [[AcousticFloorGenerator.cement_screed, 0.06, False]]),
            (0.085, base_layers + insulation_layers + [[AcousticFloorGenerator.cement_screed, 0.085, False]]),
        ]

        for screed_thickness, layers in candidates:
            result = AcousticFloorGenerator.evaluate(section, database_name, layers, screed_thickness=screed_thickness)
            if result.rw >= rw_target and result.lnw <= lnw_target:
                return result

        if AcousticFloorGenerator.is_tcc(section):
            return result

        gravel_thickness = gravel_step
        while gravel_thickness <= gravel_max + 1e-12:
            layers = base_layers + [[AcousticFloorGenerator.gravel, gravel_thickness, False],
                                    [AcousticFloorGenerator.glass_wool, False, False],
                                    [AcousticFloorGenerator.cement_screed, 0.085, False]]
            result = AcousticFloorGenerator.evaluate(
                section, database_name, layers, screed_thickness=0.085, gravel_thickness=gravel_thickness
            )
            if result.rw >= rw_target and result.lnw <= lnw_target:
                return result
            gravel_thickness += gravel_step

        return result

#-----------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------
class BeamSimpleSup:
    """
    Definiert die statischen Eigenschaften (Faktoren) eines Einfeldträgers
    :M = ql^2/8, 0
    :V = ql/2, -ql/2
    :w = 5/384·ql4/EI
    """
    def __init__(self, length):
        self.l_tot = length
        self.li_max = self.l_tot    # max span (used for calculation of admissible deflections)
        self.alpha_m = [0, 1 / 8]   # Faktor zur Berechung des Momentes unter verteilter Last
        self.alpha_v = [0, 1 / 2]   # Faktor zur Berechung der Querkarft unter verteilter Last
        self.qs_cl_erf = [3, 3]     # Querschnittsklasse: 1 == PP, 2 == EP, 3 == EE
        self.alpha_w = 5 / 384      # Faktor zur Berechung der Durchbiegung unter verteilter Last
        self.kf2 = 1.0              # Hilfsfaktor zur Brücksichtigung der Spannweitenverhältnisse bei Berechnung f1 gem. HBT, S. 46
        self.alpha_w_f_cd = 1 / 48  # Faktor zur Berechnung der Durchbiegung unter Einzellast

class BeamTwoSpan:
    def __init__(self, length):
        self.l_tot = length
        self.li_max = self.l_tot  # max span (used for calculation of admissible deflections)
        self.alpha_m = [-0.125, 0.0703]  # Faktor zur Berechung des Momentes unter verteilter Last
        self.alpha_v = [3/8, 5/8]  # Faktor zur Berechung der Querkarft unter verteilter Last
        self.qs_cl_erf = [3, 3]  # Querschnittsklasse: 1 == PP, 2 == EP, 3 == EE
        self.alpha_w = 2 / 369  # Faktor zur Berechung der Durchbiegung unter verteilter Last
        self.kf2 = 1.0  # Hilfsfaktor zur Brücksichtigung der Spannweitenverhältnisse bei Berechnung f1 gem. HBT, S. 46
        self.alpha_w_f_cd = 1/(48*5**0.5)  # Faktor zur Berechnung der Durchbiegung unter Einzellast

class BeamContinuousSupEl:
    def __init__(self, length):
        self.l_tot = length
        self.li_max = self.l_tot  # max span (used for calculation of admissible deflections)
        self.alpha_m = [-1/12, 1/24]  # Faktor zur Berechung des Momentes unter verteilter Last
        self.alpha_v = [0.5, 0.5]  # Faktor zur Berechung der Querkarft unter verteilter Last
        self.qs_cl_erf = [3, 3]  # Querschnittsklasse: 1 == PP, 2 == EP, 3 == EE
        self.alpha_w = 1 / 384  # Faktor zur Berechung der Durchbiegung unter verteilter Last
        self.kf2 = 1.0  # Hilfsfaktor zur Brücksichtigung der Spannweitenverhältnisse bei Berechnung f1 gem. HBT, S. 46
        self.alpha_w_f_cd = 1/192  # Faktor zur Berechung der Durchbiegung unter Einzellast

class BeamContinuousSupPl:
    def __init__(self, length):
        self.l_tot = length
        self.li_max = self.l_tot  # max span (used for calculation of admissible deflections)
        self.alpha_m = [-3/48, 3/48]  # Faktor zur Berechung des Momentes unter verteilter Last
        self.alpha_v = [0.5, 0.5]  # Faktor zur Berechung der Querkarft unter verteilter Last
        self.qs_cl_erf = [3, 3]  # Querschnittsklasse: 1 == PP, 2 == EP, 3 == EE
        self.alpha_w = 1 / 384  # Faktor zur Berechung der Durchbiegung unter verteilter Last
        self.kf2 = 1.0  # Hilfsfaktor zur Brücksichtigung der Spannweitenverhältnisse bei Berechnung f1 gem. HBT, S. 46
        self.alpha_w_f_cd = 1/192  # Faktor zur Berechung der Durchbiegung unter Einzellast
 
class Slab:
    """
    Nimmt die Faktoren für die Beanspruchung der Platte aus der Tabelle slab_properties.db, welche mit FE (Cedrus) ermittelt wurden
    Tabelle wird direkt im Skript "create_slab_properties.py" erstellt.
    """

    _property_cache = {}
    _available_entries = None
    _database_path = Path(__file__).resolve().with_name("slab_properties.db")

    @staticmethod
    def calc_alpha_w_f_cd(alpha_w):
        # slab_properties stores the uniform-load deflection coefficient W.
        # Derive an equivalent point-load coefficient from the beam ratio (approximation)
        # (P L^3 / 48 EI) / (5 q L^4 / 384 EI) = 1.6 instead of using a dummy.
        return 1.6 * abs(alpha_w)

    def __init__(self, length_x, length_y, support, column_width=0.25, column_length=0.25,
                 column_ke=0.9, column_tributary_area=None):
        self.raender = support
        self.lx = length_x
        self.ly = length_y
        self.li_max = max(length_x, length_y)
        self.l_tot = max(length_x, length_y)
        self.has_columns = support in ("PL-eingespannt", "drop_beam")
        self.column_width = column_width
        self.column_length = column_length
        self.column_ke = column_ke #0.9 for internal columns
        self.column_tributary_area = column_tributary_area if column_tributary_area is not None else length_x * length_y
        property_key = (self.raender, self.lx, self.ly)
        if property_key not in self._property_cache:
            conn = sqlite3.connect(self._database_path)
            cursor = conn.cursor()
            result = cursor.execute(
                        """
                        SELECT NAME, RAENDER, LX, LY, MX_POS, MX_NEG, MY_POS, MY_NEG, V_POS, V_NEG, W, F 
                        FROM slab_properties
                        WHERE RAENDER = ? AND LX = ? AND LY = ? """, property_key).fetchall()
            if result:
                self._property_cache[property_key] = result[0]
            elif self._available_entries is None:
                self.__class__._available_entries = cursor.execute(
                    """
                    SELECT DISTINCT RAENDER, LX, LY
                    FROM slab_properties
                    ORDER BY RAENDER, LX, LY
                    """
                ).fetchall()
            conn.close()

        if property_key not in self._property_cache:
            raise ValueError(
                f"No slab_properties entry for support={self.raender!r}, LX={self.lx}, LY={self.ly}. "
                f"Use one of the available entries: {self._available_entries}"
            )
        self.result = self._property_cache[property_key]
        #Faktor alpha_m_x: Bewehrungfür l_max
        #x-Richtung = Richtung mit maximaler Spannweite
        self.alpha_m_x = (float(self.result[4]), float(self.result[5])) #positive and negative moment
        #Faktor alpha_m_x: Bewehrungfür l_min
        #y-Ritchtun = Richtung mit minimaler Spannweite
        self.alpha_m_y = (float(self.result[6]), float(self.result[7])) #positive and negative moment
        self.alpha_v = (float(self.result[8]), float(self.result[9])) #positive and negative shear
        self.qs_cl_erf = [2, 1]
        self.alpha_w = float(self.result[10])
        self.kf2 = float(self.result[11]) # Hilfsfaktor zur Brücksichtigung der Spannweitenverhältnisse bei Berechnung f1 gem. HBT, S. 46 aus ZC1 Grundlagen Baudynamik
        self.alpha_w_f_cd = self.calc_alpha_w_f_cd(self.alpha_w)

        #self.factors = [self.alpha_m, self.alpha_v, self.qs_cl_erf, self.alpha_w, self.kf2, self.alpha_w_f_cd]

class LoadCombinations:
    def __init__(self, g0k, g1k, g2k, qk=2e3, psi=[0.7, 0.5, 0.3], gamma_g=1.35, gamma_q=1.5):
        self.g0k = g0k #selfweight of the structural element
        self.g1k = g1k #dead load of the floor structure
        self.g2k = g2k #superimposed dead load
        self.qk = qk #live loads
        self.psi = psi #psi factors for combination of actions
        self.gamma_g = gamma_g #partial safety factor for permanent loads
        self.gamma_q = gamma_q #partial safety factor for variable loads
        self.gk = g0k + g1k + g2k

    def uls(self):
        return self.gamma_g * (self.g0k + self.g1k + self.g2k) + self.gamma_q * self.qk
    
    def uls_short(self):
        return self.gamma_q * self.psi[0] * self.qk #short-term combination for short-term effects
    
    def uls_per(self):
        return self.gamma_g * (self.g0k + self.g1k + self.g2k) + self.gamma_q * (1-self.psi[0]) * self.qk #quasi-permanent combination for long-term effects
    
    def sls_rare(self):
        return self.g0k + self.g1k + self.g2k + self.qk
    
    def sls_freq(self):
        return self.g0k + self.g1k + self.g2k + self.psi[1] * self.qk
    
    def sls_per(self):
        return self.g0k + self.g1k + self.g2k + self.psi[2] * self.qk
    


class Member1D:
    def __init__(self, section, system, floorstruc, requirements, g2k=0.0, qk=2e3, psi0=0.7, psi1=0.5, psi2=0.3,
                 fire=None):
        self.section = section
        self.system = system
        self.floorstruc = floorstruc
        self.requirements = requirements
        self.acoustic = AcousticFloorGenerator.evaluate_floorstruc(section, floorstruc)
        rw_target, lnw_target = AcousticFloorGenerator.target_values(section, self.requirements.acoustic)
        self.acoustic_verified = (
            self.acoustic.rw >= rw_target
            and self.acoustic.lnw <= lnw_target
        )
        self.li_max = self.system.li_max

        # Initialize LoadCombinations
        self.load_combinations = LoadCombinations(
            g0k=self.section.g0k,
            g1k=self.floorstruc.gk_area,
            g2k=g2k,
            qk=qk,
            psi=[psi0, psi1, psi2]
        )
        self.g0k = self.section.g0k
        self.g1k = self.load_combinations.g1k
        self.g2k = self.load_combinations.g2k
        self.gk = self.load_combinations.gk
        self.qk = self.load_combinations.qk
        self.psi = self.load_combinations.psi
        self.q_rare = self.load_combinations.sls_rare()
        self.q_freq = self.load_combinations.sls_freq()
        self.q_per = self.load_combinations.sls_per()
        self.q_uls = self.load_combinations.uls()
        self.gamma_g = self.load_combinations.gamma_g
        self.gamma_q = self.load_combinations.gamma_q

        self.m = self.q_per / 10 # Mass per unit length in kg/m, assuming q_per is in N/m and dividing by 10 to convert to kg/m (assuming g=10 m/s^2)
        self.w_install_adm = self.system.li_max / self.requirements.lw_install
        self.w_use_adm = self.system.li_max / self.requirements.lw_use
        self.w_app_adm = self.system.li_max / self.requirements.lw_app
        self.mkd_p = self.system.alpha_m[0] * (self.gk + self.qk) * self.system.l_tot ** 2
        self.mkd_n = self.system.alpha_m[1] * (self.gk + self.qk) * self.system.l_tot ** 2
        self.qk_zul_gzt = float
        if fire is not None:
            self.fire = fire
        else: 
            self.fire = [1, 0, 0, 0] #default: no fire only on bottom

        # calculation of deflections uncracked (plus cracked for concrete sections self.section.section_type[0:2] = rc))
        section_material = self.section.section_type[0:2]

        unit_def = self.system.alpha_w * self.system.l_tot ** 4 / self.section.ei1  # deflection for q = 1, phi = 0

        if self.requirements.install == "ductile":
            self.w_install = unit_def * (self.q_freq + self.q_per * (self.section.phi - 1))
            if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
                self.w_install_ger = unit_def * (
                        self.q_per * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs, self.section.phi,
                                                                 self.section.h, self.section.d)
                        + (self.q_freq - self.q_per) * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs,
                                                                                   0, self.section.h, self.section.d)
                        - self.q_per
                )
            if section_material == "tc":
                #Not adjusting for installation time
                #self.w_install = unit_def*self.section.ei1 * (self.q_per / self.section.EI_SLS[1] + (self.q_freq - self.q_per) / self.section.EI_SLS[0])
                #Adjusting for installation time by substracting the elastic deflection due to permanent loads
                self.w_install = unit_def*self.section.ei1 * (self.q_per / self.section.EI_SLS[1] - self.q_per / self.section.EI_SLS[0] + (self.q_freq - self.q_per) / self.section.EI_SLS[0])

        elif self.requirements.install == "brittle":
            self.w_install = unit_def * (self.q_rare + self.q_per * (self.section.phi - 1))
            if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
                self.w_install_ger = unit_def * (
                        self.q_per * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs, self.section.phi,
                                                                 self.section.h, self.section.d)
                        + (self.q_rare - self.q_per) * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs,
                                                                                   0, self.section.h, self.section.d)
                        - self.q_per
                )
            if section_material == "tc":
                #Not adjusting for installation time
                #self.w_install = unit_def*self.section.ei1 * (self.q_per / self.section.EI_SLS[1] + (self.q_rare - self.q_per) / self.section.EI_SLS[0])
                #Adjusting for installation time by substracting the elastic deflection due to permanent loads
                self.w_install = unit_def*self.section.ei1 * (self.q_per / self.section.EI_SLS[1] - self.q_per / self.section.EI_SLS[0] + (self.q_freq - self.q_per) / self.section.EI_SLS[0])

        self.w_use = unit_def * (self.q_freq - self.gk)
        if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
            self.w_use_ger = unit_def * (
                    (self.q_freq - self.q_per) * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs, 0,
                                                                             self.section.h, self.section.d)
            )
        if section_material == "tc":
            self.w_use = unit_def*self.section.ei1 * (
                    (self.q_freq - self.q_per) / self.section.EI_SLS[0]
            )
        self.w_app = unit_def * (self.q_per * (1 + self.section.phi))
        if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
            self.w_app_ger = unit_def * (
                    self.q_per * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs, self.section.phi,
                                                             self.section.h, self.section.d)
            )
        if section_material == "tc":
            self.w_app = unit_def*self.section.ei1 * (
                    self.q_per / self.section.EI_SLS[1]
            )
        self.co2 = system.l_tot * (self.floorstruc.co2 + self.section.co2)

        # calculation first frequency (uncracked cross-section, method for cracked cross-section is not implemented jet)
        self.f1 = self.calc_f1()
        # calculation of further vibration criteria for wooden cross-sections
        section_material = self.section.section_type[0:2]
        if section_material == "wd" or section_material == "rc" or section_material == "tc":  # check for material type
            self.ei_b = max(self.section.ei_b,
                            self.floorstruc.ei)  # Berücksichtigung n.t. Bodenaufbau gemäss Beispielsammlung HBT)
            self.bm_rech = self.system.li_max / 1.1 * (self.ei_b / self.section.ei1) ** 0.25  # HBT Seite 46
            self.a_ed = self.calc_vib1()
            self.wf_ed, self.ve_ed = self.calc_vib2()
            if self.section.xi < 0.015:
                self.r1 = 1.0  # HBT S. 48
            elif self.section.xi < 0.025:
                self.r1 = 1.15  # HBT S. 48
            else:
                self.r1 = 1.25  # HBT S. 48
            self.ve_cd = self.requirements.alpha_ve_cd * 100 ** (self.f1 * self.section.xi - 1)

    def calc_qu(self):
        # calculates maximal load qu in respect to bearing moment mu_max, mu_min and static system
        alpha_m = self.system.alpha_m
        alpha_v = self.system.alpha_v
        qs_class_erf = self.system.qs_cl_erf  # z.B. [0, 2]
        qs_class_vorh = [self.section.qs_class_n, self.section.qs_class_p]

        def finalize(qu_bend, qu_shear):
            self.qu_bending = qu_bend
            self.qu_shear = qu_shear
            self.uls_governing_mode = "bending" if qu_bend <= qu_shear else "shear"
            return min(qu_bend, qu_shear)

        if self.section.section_type == "rc_rib":
            v_pos = getattr(self.section, "vu_PB_p", self.section.vu_p)
            v_neg = abs(getattr(self.section, "vu_PB_n", self.section.vu_n))
        else:
            v_pos = self.section.vu_p
            v_neg = abs(self.section.vu_n)

        shear_candidates = []
        for alpha in alpha_v:
            if abs(alpha) <= 1e-12:
                continue
            v_rd = v_pos if alpha > 0 else v_neg
            shear_candidates.append(v_rd / (abs(alpha) * self.system.l_tot))
        qu_shear = max(min(shear_candidates), 0.0) if shear_candidates else float("inf")

        if self.section.section_type == "rc_rib":
            # Ribbed concrete has different resistance mechanisms in span and over supports:
            # positive bending is governed by rib reinforcement, while negative bending is governed
            # by the upper flange reinforcement. Therefore both moment signs are checked explicitly.
            def rib_bending_capacity(alpha, mu_rd, mr, qs_class, x, d, qs_class_required):
                if abs(alpha) <= 1e-12:
                    return float("inf")
                factor = 1.0
                if qs_class > qs_class_required:
                    epsilon = 1.0e-3
                    shift = 0.35 if qs_class == 1 else 0.5
                    x_d = x / d if d > 0 else float("inf")
                    factor = min(
                        0.5 * (1 + 2 / np.pi * np.arctan((abs(mu_rd) - abs(mr)) / epsilon)),
                        1 - 0.5 * (1 + 2 / np.pi * np.arctan((x_d - shift) / epsilon)),
                    )
                q_cap = factor * mu_rd / (alpha * self.system.l_tot ** 2)
                return max(q_cap, 0.0)

            bending_candidates = [
                rib_bending_capacity(
                    alpha_m[0], self.section.mu_min, self.section.mr_pb_n,
                    self.section.qs_class_n, self.section.x_PB_n, self.section.ds_PB,
                    qs_class_erf[0],
                ),
                rib_bending_capacity(
                    alpha_m[1], self.section.mu_max, self.section.mr_pb_p,
                    self.section.qs_class_p, self.section.x_PB_p, self.section.d_PB,
                    qs_class_erf[1],
                ),
            ]
            qu_bend = min(bending_candidates)
            return finalize(qu_bend, qu_shear)

        if min(alpha_m) >= 0 or abs(alpha_m[1]) >= abs(alpha_m[0]):
            if qs_class_vorh[1] <= qs_class_erf[1]:
                # if cross-section fulfills the ductility criterion (e.g. required: PP, present PP) then assign the full
                # bending strength
                qu_bend = self.section.mu_max / (max(alpha_m) * self.system.l_tot ** 2)
            else:
                # if the cross-section is not fulfilling the ductility criterion (e.g. required: EP, present PP) then
                # assign a value, which drops from the full bending strength fast towards 0 (for concrete sections)
                # or a value of 0 (for all other sections)
                if self.section.section_type[0:2] == "rc":
                    # for reinforced concthurete cross-sections: smooth change to 0 load bearing capacity when roh<roh_min
                    # or roh>roh_zul (enables more efficient optimization)
                    epsilon = 1.0e-3
                    if qs_class_vorh[1] == 1:
                        shift = 0.35
                    else:
                        shift = 0.5
                    x_d = self.section.x_p / self.section.d
                    factor = min(0.5 * (1 + 2 / np.pi * np.arctan((self.section.mu_max - self.section.mr_p) / epsilon)),    #README: Wieso wird hier mit diesem factor gearbeitet? und nicht ienfahc mit qu_bend = 0 wie beim Mehrfehldträger?
                                 1 - 0.5 * (1 + 2 / np.pi * np.arctan((x_d - shift) / epsilon)))
                    qu_bend = factor * self.section.mu_max / (max(alpha_m) * self.system.l_tot ** 2)
                else:
                    # for all other cross-sections bending strength = 0
                    qu_bend = 0
        else:
            if qs_class_vorh[0] <= qs_class_erf[0]:
                qu_bend = self.section.mu_min / (min(alpha_m) * self.system.l_tot ** 2)
            else:
                # if the cross-section is not fulfilling the ductility criterion (e.g. required: EP, present PP) then
                # assign a value, which drops from the full bending strength fast towards 0 (for concrete sections)
                # or a value of 0 (for all other sections)
                if self.section.section_type[0:2] == "rc":
                    # for reinforced concrete cross-sections: smooth change to 0 load bearing capacity when roh<roh_min
                    # or roh>roh_zul (enables more efficient optimization)
                    epsilon = 1.0e-3
                    if qs_class_vorh[0] == 1:
                        shift = 0.35
                    else:
                        shift = 0.5
                    x_d = self.section.x_n / self.section.d
                    factor = min(0.5 * (1 + 2 / np.pi * np.arctan((self.section.mu_min - self.section.mr_n) / epsilon)),
                                 1 - 0.5 * (1 + 2 / np.pi * np.arctan((x_d - shift) / epsilon)))
                    qu_bend = factor * self.section.mu_min / (min(alpha_m) * self.system.l_tot ** 2)
                else:
                    # for all other cross-sections bending strength = 0
                    qu_bend = 0
        return finalize(qu_bend, qu_shear)

    def calc_qk_zul_gzt(self):
        self.qk_zul_gzt = 0
        if self.section.section_type == "tcc":
            def component_qk_zul(qu_0_component, qu_inf_component):
                if np.isnan(qu_0_component) or np.isnan(qu_inf_component):
                    return float("nan")
                if not np.isfinite(qu_0_component) and not np.isfinite(qu_inf_component):
                    return float("inf")
                if qu_0_component <= 0 or qu_inf_component <= 0:
                    return 0.0
                deg_util_gd_component = 1.25 * self.gk * self.gamma_g / qu_inf_component
                deg_util_qd_inf_component = 1.25 * (1 - self.psi[0]) * self.gamma_q / qu_inf_component
                deg_util_qd_0_component = self.psi[0] * self.gamma_q / qu_0_component
                denominator = deg_util_qd_inf_component + deg_util_qd_0_component
                if denominator <= 0:
                    return float("inf")
                return max((1 - deg_util_gd_component) / denominator, 0.0)

            # Capacity at t=0
            self.section.mu_max = self.section.Mu[0]
            self.section.vu_p = self.section.Vu[0]
            qu_0 = self.calc_qu()  # Entspricht der reinen Tragfähigkeit bei t=0
            qu_0_bending = getattr(self, "qu_bending", float("nan"))
            qu_0_shear = getattr(self, "qu_shear", float("nan"))
            
            # Capacity at t=inf
            self.section.mu_max = self.section.Mu[1]
            self.section.vu_p = self.section.Vu[1]
            qu_inf = self.calc_qu() # Entspricht der reinen Tragfähigkeit bei t=inf
            qu_inf_bending = getattr(self, "qu_bending", float("nan"))
            qu_inf_shear = getattr(self, "qu_shear", float("nan"))

            #Set dummy value again for mu_max and vu_p
            self.section.mu_max = 1
            self.section.vu_p = 1

            # Calculate degrees of utilization for permanent loads
            # Quasi-permament 125% to cover 3...7years check 
            deg_util_gd = 1.25 * self.gk * self.gamma_g / qu_inf 
            deg_util_qd_inf = 1.25 * (1 - self.psi[0]) * self.gamma_q / qu_inf # Quasi-permament of variable loads
            deg_util_qd_0 = self.psi[0] * self.gamma_q / qu_0 # Short-term of variable loads
            
            # Negative values are wanted for optimization 
            self.qk_zul_gzt = (1 - deg_util_gd) / (deg_util_qd_inf + deg_util_qd_0)
            self.qk_zul_bending_gzt = component_qk_zul(qu_0_bending, qu_inf_bending)
            self.qk_zul_shear_gzt = component_qk_zul(qu_0_shear, qu_inf_shear)
            if self.qk_zul_bending_gzt <= self.qk_zul_shear_gzt:
                self.uls_governing_mode = "bending"
            else:
                self.uls_governing_mode = "shear"

        else:
            # Standard calc. (Concrete, Wood, etc.)
            self.qu = self.calc_qu()
            self.qk_zul_gzt = max((self.qu - self.gamma_g * self.gk) / self.gamma_q, 0)
            qu_bending = getattr(self, "qu_bending", float("nan"))
            qu_shear = getattr(self, "qu_shear", float("nan"))
            self.qk_zul_bending_gzt = (
                max((qu_bending - self.gamma_g * self.gk) / self.gamma_q, 0)
                if np.isfinite(qu_bending)
                else float("inf")
            )
            self.qk_zul_shear_gzt = (
                max((qu_shear - self.gamma_g * self.gk) / self.gamma_q, 0)
                if np.isfinite(qu_shear)
                else float("inf")
            )

        return self.qk_zul_gzt

    def calc_f1(self):
        # calculates first frequency of system according to HBT, Seite 46
        kf2 = self.system.kf2
        l_rech = self.system.li_max
        section_material = self.section.section_type[0:2]
        if section_material == "rc":  # take cracked stiffness for calculation of concrete sections if section is cracked
            if concrete_member_is_uncracked(self):
                eil = self.section.ei1
            else:
                eil = self.section.ei2
        else:
            eil = self.section.ei1
        m = self.m
 #       print("m =", m)
        
        f1 = kf2 * np.pi / (2 * (l_rech) ** 2) * (abs(eil) / abs(m))**0.5  # HBT, Seite 46    #FEHLER WARNUNG IN COMPARISON ULS SLS
        return f1

    def calc_vib1(self, f0=700):
        # calculates a_Ed according to HBT, Seite 47
        f1 = self.f1
        if f1 <= 1e-9:
            return float("inf")
        m_gen = self.m * self.system.li_max / 2 * self.bm_rech
        xi = self.section.xi
        if f1 <= 5.1:
            alpha = 0.2
            ff = f1
        elif f1 <= 6.9:
            alpha = 0.06
            ff = f1
        else:
            alpha = 0.06
            ff = 6.9
        a_ed = 0.4 * f0 * alpha / m_gen * 1 / (((f1 / ff) ** 2 - 1) ** 2 + (2 * xi * f1 / ff) ** 2)**0.5  # HBT, Seite 47
        return a_ed

    def calc_vib2(self, f=1000):
        # calculates W_F,ED according to to HBT, Seite 48
        wf_ed = self.system.alpha_w_f_cd * f * self.system.li_max ** 3 / (self.bm_rech * self.section.ei1)
        

        section_material = self.section.section_type[0:2]
        if section_material == "rc":  # take cracked stiffness for calculation of concrete sections
            eil = self.section.ei2
        else:
            eil = self.section.ei1
        ve_ed = 364 / (abs(self.bm_rech) * (abs(self.m) ** 3 * abs(eil) * 1e6)**0.25)        #FEHLER WARNUNG IN COMPARISON ULS SLS
        return wf_ed, ve_ed

    def get_fire_resistance(self):
        # evaluate fire resistance
        if self.section.section_type == "rc_rec":
            fire_resistance = RectangularConcrete.fire_resistance(self.section)
        elif self.section.section_type == "wd_rec":
            fire_resistance = RectangularWood.fire_resistance(self)
        elif self.section.section_type == "rc_rib":
            fire_resistance = RibbedConcrete.fire_resistance(self.section)
        elif self.section.section_type == "wd_rib":
            fire_resistance = RibWood.fire_resistance(self.section)
        elif self.section.section_type == "tcc":
            fire_resistance = TCC.fire_resistance(self)
        else:
            #print("fire resistance for is not defined for that cross-section type.")
            fire_resistance = None
        self.fire_resistance = fire_resistance

class Member2D:
    def __init__(self, section, system, floorstruc, requirements, g2k=0.0, qk=2e3, psi0=0.7, psi1=0.5, psi2=0.3,
                     fire_b=True, fire_l=False, fire_t=False, fire_r=False, evaluate_service=True,
                     check_punching=True, uls_bending_only=False,
                     optimize_shear_reinforcement=True):
        """
        Definiert ein 2-Dimensionales Bauteil (Platte) mit Eigenschaften
        :section:
        :system:
        """
        self.section = section
        self.system = system
        self.check_punching = check_punching
        self.uls_bending_only = uls_bending_only
        self.optimize_shear_reinforcement = optimize_shear_reinforcement
        self.floorstruc = floorstruc
        self.requirements = requirements
        self.acoustic = AcousticFloorGenerator.evaluate_floorstruc(section, floorstruc)
        rw_target, lnw_target = AcousticFloorGenerator.target_values(section, self.requirements.acoustic)
        self.acoustic_verified = (
            self.acoustic.rw >= rw_target
            and self.acoustic.lnw <= lnw_target
        )
        self.li_min = min(self.system.lx, self.system.ly)
        self.li_max = self.system.li_max
        # Initialize LoadCombinations
        self.load_combinations = LoadCombinations(
            g0k=self.section.g0k,
            g1k=self.floorstruc.gk_area,
            g2k=g2k,
            qk=qk,
            psi=[psi0, psi1, psi2]
        )
        self.g0k = self.section.g0k
        self.g1k = self.load_combinations.g1k
        self.g2k = self.load_combinations.g2k
        self.gk = self.load_combinations.gk
        self.qk = self.load_combinations.qk
        self.psi = self.load_combinations.psi
        self.q_rare = self.load_combinations.sls_rare()
        self.q_freq = self.load_combinations.sls_freq()
        self.q_per = self.load_combinations.sls_per()
        self.qu = self.load_combinations.uls()

        self.m = self.q_per / 10
        self.w_install_adm = self.li_min / self.requirements.lw_install
        self.w_use_adm = self.li_min / self.requirements.lw_use
        self.w_app_adm = self.li_min / self.requirements.lw_app
        self.mkd_p = self.system.alpha_m_x[0] * (self.gk + self.qk) * self.li_max ** 2
        self.mkd_n = self.system.alpha_m_x[1] * (self.gk + self.qk) * self.li_max ** 2
        self.mkd_p_y = self.system.alpha_m_y[0] * (self.gk + self.qk) * self.li_min ** 2
        self.mkd_n_y = self.system.alpha_m_y[1] * (self.gk + self.qk) * self.li_min ** 2
        self.qk_zul_gzt = float
        self.fire = [0, 0, 0, 0]  # fire from bottom, left, top, right (0: no fire; 1: fire)
        if fire_b is True:
            self.fire[0] = 1
        if fire_l is True:
            self.fire[1] = 1
        if fire_t is True:
            self.fire[2] = 1
        if fire_r is True:
            self.fire[3] = 1
        self.fire_resistance = []
        self.punching_vrds_required = 0.0
        self.co2 = system.l_tot * (self.floorstruc.co2 + self.section.co2)

        if not evaluate_service:
            self.w_install = 0.0
            self.w_use = 0.0
            self.w_app = 0.0
            self.w_install_ger = 0.0
            self.w_use_ger = 0.0
            self.w_app_ger = 0.0
            self.f1 = 0.0
            self.a_ed = 0.0
            self.wf_ed = 0.0
            self.ve_cd = 0.0
            self.ve_ed = 0.0
            self.r1 = 1.15
            return

        # calculation of deflections uncracked (plus cracked for concrete sections self.section.section_type[0:2] = rc))
        section_material = self.section.section_type[0:2]
        unit_def = self.system.alpha_w * self.system.l_tot ** 4 / self.section.ei1  # deflection for q = 1, phi = 0


        if self.requirements.install == "ductile":
            self.w_install = unit_def * (self.q_freq + self.q_per * (self.section.phi - 1))
            if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
                self.w_install_ger = unit_def * (
                        self.q_per * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs, self.section.phi, self.section.h, self.section.d)
                        + (self.q_freq - self.q_per) * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs,0, self.section.h,self.section.d)
                        - self.q_per
                        )
            elif section_material == "pc":
                M_sec_x, _, _ = self.section.get_secondaryInternalForces(self.system)
                alpha_m_x = max(abs(self.system.alpha_m_x[0]), abs(self.system.alpha_m_x[1])) #maximum alpha_m_x
                # Calculate MEd_SLS based on the maximum alpha_m_x and the total load q_freq-g0k as this is the deviation force of the pt system
                MEd_SLS = (self.q_freq-self.g0k) * alpha_m_x * self.system.l_tot ** 2
                M_sec = M_sec_x[0] if abs(M_sec_x[0]) >= abs(M_sec_x[1]) else M_sec_x[1] #select maximum moment for calculation of deflection
                _, ei_eff, _ = self.section.calc_EIeff(self.section.Px_total, self.system.l_tot, MEd_SLS, M_sec, self.section.m_r)
                unit_def_pc = self.system.alpha_w * self.system.l_tot ** 4 / ei_eff
                self.w_install = unit_def_pc * ((self.q_freq-self.g0k) + (self.q_per-self.g0k) * (self.section.phi - 1))
        elif self.requirements.install == "brittle":
            self.w_install = unit_def * (self.q_rare + self.q_per * (self.section.phi - 1))
            if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
                    self.w_install_ger = unit_def * (
                    self.q_per * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs, self.section.phi, self.section.h, self.section.d)
                    + (self.q_rare - self.q_per) * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs,0, self.section.h, self.section.d)
                    - self.q_per
                    )
        self.w_use = unit_def * (self.q_freq - self.gk)
        if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
            self.w_use_ger = unit_def * (
                        (self.q_freq - self.q_per) * RectangularConcrete.f_w_ger(self.section.roh,
                                                                                 self.section.rohs, 0,
                                                                                 self.section.h, self.section.d)
                )
        elif section_material == "pc":
            M_sec_x, _, _ = self.section.get_secondaryInternalForces(self.system)
            alpha_m_x = max(abs(self.system.alpha_m_x[0]), abs(self.system.alpha_m_x[1]))
            MEd_SLS = (self.q_freq - self.g0k) * alpha_m_x * self.system.l_tot ** 2
            M_sec = M_sec_x[0] if abs(M_sec_x[0]) >= abs(M_sec_x[1]) else M_sec_x[1]
            _, ei_eff, _ = self.section.calc_EIeff(self.section.Px_total, self.system.l_tot, MEd_SLS, M_sec, self.section.m_r)
            unit_def_pc = self.system.alpha_w * self.system.l_tot ** 4 / ei_eff
            self.w_use = unit_def_pc * ((self.q_freq - self.g0k) + (self.q_per - self.g0k) * (self.section.phi - 1))
        self.w_app = unit_def * (self.q_per * (1 + self.section.phi))
        if section_material == "rc":  # Alternative Durchbiegungsberechnung für Betonquerschnitte gem. SIA262,(102)
            self.w_app_ger = unit_def * (
                    self.q_per * RectangularConcrete.f_w_ger(self.section.roh, self.section.rohs,
                                                             self.section.phi,
                                                             self.section.h, self.section.d)
                )
        elif section_material == "pc":
            M_sec_x, _, _ = self.section.get_secondaryInternalForces(self.system)
            alpha_m_x = max(abs(self.system.alpha_m_x[0]), abs(self.system.alpha_m_x[1]))
            MEd_SLS = (self.q_per-self.g0k) * alpha_m_x * self.system.l_tot ** 2
            M_sec = M_sec_x[0] if abs(M_sec_x[0]) >= abs(M_sec_x[1]) else M_sec_x[1]
            _, ei_eff, _ = self.section.calc_EIeff(self.section.Px_total, self.system.l_tot, MEd_SLS, M_sec, self.section.m_r)
            unit_def_pc = self.system.alpha_w * self.system.l_tot ** 4 / ei_eff
            self.w_app = unit_def_pc * ((self.q_per-self.g0k) * (1 + self.section.phi))
        # calculation first frequency and vibration criteria
        self.f1 = self.calc_f1()
        self.a_ed = 0
        self.wf_ed = 0
        self.ve_cd = 0
        self.ve_ed = 0
        self.r1 = 1.15
        if section_material in ("wd", "rc", "pc", "tc"):
            self.ei_b = max(getattr(self.section, "ei_b", self.section.ei1), self.floorstruc.ei)
            self.bm_rech = self.system.li_max / 1.1 * (self.ei_b / self.section.ei1) ** 0.25
            self.a_ed = self.calc_vib1()
            self.wf_ed, self.ve_ed = self.calc_vib2()
            if self.section.xi < 0.015:
                self.r1 = 1.0
            elif self.section.xi < 0.025:
                self.r1 = 1.15
            else:
                self.r1 = 1.25
            self.ve_cd = self.requirements.alpha_ve_cd * 100 ** (self.f1 * self.section.xi - 1)

    def should_check_punching(self):
        return bool(self.check_punching and getattr(self.system, "has_columns", False))

    def uls_redistributed_moment_factors(self):
        elastic_factors = (self.system.alpha_m_x, self.system.alpha_m_y)
        factors = { #factors for plastic redistribution of moments
            "LL-eingespannt": (1.51, 0.76),
            "PL-eingespannt": (1.47, 0.68),
        }.get(self.system.raender)
        if factors is None:
            return elastic_factors

        if self.section.section_type not in ("rc_rec", "pc_rec"):
            return elastic_factors

        #Check wheter cross section allows for plastic redistribution in bending according to ductility classes
        qs_class_vorh = [self.section.qs_class_n, self.section.qs_class_p]
        if not (
            qs_class_vorh[0] <= self.system.qs_cl_erf[0]
            and qs_class_vorh[1] <= self.system.qs_cl_erf[1]
        ):
            return elastic_factors

        pos_factor, neg_factor = factors

        def redistribute(alpha_m):
            return tuple(
                alpha * (pos_factor if alpha >= 0 else neg_factor)
                for alpha in alpha_m
            )

        return redistribute(self.system.alpha_m_x), redistribute(self.system.alpha_m_y)

    def calc_qu(self):
        """
        Idea: qu von maximaler Spannweite definiert
        Schauen, welche Nachweise man alles in beide Richtungen machen muss und bei welchen einfach l_max ausreicht!
        """
        # calculates maximal load qu in respect to bearing moment mu_max, mu_min and static system
        alpha_m, _ = self.uls_redistributed_moment_factors()
        alpha_v = self.system.alpha_v
        qs_class_erf = self.system.qs_cl_erf  # z.B. [0, 2]
        qs_class_vorh = [self.section.qs_class_n, self.section.qs_class_p]

        def finalize(qu_bend, qu_shear):
            if self.uls_bending_only:
                qu_shear = float("inf")
            self.qu_bending = qu_bend
            self.qu_shear = qu_shear
            if qu_bend <= qu_shear:
                self.uls_governing_mode = "bending"
            else:
                self.uls_governing_mode = "punching" if self.should_check_punching() else "shear"
            return min(qu_bend, qu_shear)

        if self.section.section_type == "pc_rec":
            m_sec_x, _, _ = self.section.get_secondaryInternalForces(self.system)
            q_bend_candidates = []
            self.pt_uls_m_rd_pos = self.section.mu_max
            self.pt_uls_m_rd_neg = self.section.mu_min
            self.pt_uls_m_sec_pos = m_sec_x[0]
            self.pt_uls_m_sec_neg = m_sec_x[1]
            self.pt_uls_q_bend_pos = float("nan")
            self.pt_uls_q_bend_neg = float("nan")

            def pt_ductility_factor(qs_class, x_d, m_rd, m_r):
                if qs_class <= 1:
                    shift = 0.35
                else:
                    shift = 0.50
                epsilon = 1.0e-3
                resistance_factor = 0.5 * (
                    1 + 2 / np.pi * np.arctan((abs(m_rd) - abs(m_r)) / epsilon)
                )
                ductility_factor = 1 - 0.5 * (
                    1 + 2 / np.pi * np.arctan((x_d - shift) / epsilon)
                )
                return min(resistance_factor, ductility_factor)

            for alpha_i, m_sec_i, m_rd_i in (
                (alpha_m[0], m_sec_x[0], self.section.mu_max),
                (alpha_m[1], m_sec_x[1], self.section.mu_min),
            ):
                if abs(alpha_i) <= 1e-12:
                    continue
                if alpha_i >= 0:
                    qs_class_i = self.section.qs_class_p
                    x_d_i = self.section.x_p / self.section.d
                else:
                    qs_class_i = self.section.qs_class_n
                    x_d_i = self.section.x_n / self.section.ds
                min_reinf_mr = getattr(self.section, "m_r_min_reinf", self.section.m_r)
                factor_i = pt_ductility_factor(qs_class_i, x_d_i, m_rd_i, min_reinf_mr)
                q_cap = (factor_i * m_rd_i - m_sec_i) / (alpha_i * self.system.l_tot ** 2)
                q_bend_candidates.append(q_cap)
                if alpha_i >= 0:
                    self.pt_uls_q_bend_pos = q_cap
                else:
                    self.pt_uls_q_bend_neg = q_cap
            qu_bend = max(min(q_bend_candidates), 0.0) if q_bend_candidates else float("inf")
            if self.should_check_punching():
                qu_shear = self.calc_punching_qu()
            else:
                qu_shear = self.calc_shear_qu()
            return finalize(qu_bend, qu_shear)

        if min(alpha_m) == 0:
            if qs_class_vorh[1] <= qs_class_erf[1]:
                # if cross-section fulfills the ductility criterion (e.g. required: PP, present PP) then assign the full
                # bending strength
                qu_bend = self.section.mu_max / (max(alpha_m) * self.system.l_tot ** 2)
            else:
                # if the cross-section is not fulfilling the ductility criterion (e.g. required: EP, present PP) then
                # assign a value, which drops from the full bending strength fast towards 0 (for concrete sections)
                # or a value of 0 (for all other sections)
                if self.section.section_type[0:2] in ("rc", "pc"):
                    # for reinforced concrete cross-sections: smooth change to 0 load bearing capacity when roh<roh_min
                    # or roh>roh_zul (enables more efficient optimization)
                    epsilon = 1.0e-3
                    if qs_class_vorh[1] == 1:
                        shift = 0.35
                    else:
                        shift = 0.5
                    x_d = self.section.x_p / self.section.d
                    cracking_moment = self.section.mr_p if self.section.section_type[0:2] == "rc" else self.section.m_r
                    factor = min(0.5 * (1 + 2 / np.pi * np.arctan((self.section.mu_max - cracking_moment) / epsilon)),    #README: Wieso wird hier mit diesem factor gearbeitet? und nicht ienfahc mit qu_bend = 0 wie beim Mehrfehldträger?
                                 1 - 0.5 * (1 + 2 / np.pi * np.arctan((x_d - shift) / epsilon)))
                    qu_bend = factor * self.section.mu_max / (max(alpha_m) * self.system.l_tot ** 2)
                else:
                    # for all other cross-sections bending strength = 0
                    qu_bend = 0
            if self.should_check_punching():
                qu_shear = self.calc_punching_qu()
            else:
                qu_shear = self.calc_shear_qu()
        else:
            if qs_class_vorh[0] <= qs_class_erf[0] and qs_class_vorh[1] <= qs_class_erf[1]:
                qu_bend = min(self.section.mu_max / (max(alpha_m) * self.system.l_tot ** 2), self.section.mu_min /
                              (min(alpha_m) * self.system.l_tot ** 2))
            else:
                qu_bend = 0
            if self.should_check_punching():
                qu_shear = self.calc_punching_qu()
            else:
                qu_shear = self.calc_shear_qu()
        return finalize(qu_bend, qu_shear)

    def calc_shear_qu(self):
        candidates = []
        for i, alpha_v in enumerate(self.system.alpha_v):
            if abs(alpha_v) <= 1e-12:
                continue
            v_rd = self.section.vu_p if alpha_v > 0 else abs(self.section.vu_n)
            p_sin = self.calc_shear_prestress_deviation_force()
            v_sec = self.calc_shear_secondary_force(i)
            candidates.append((v_rd + p_sin - v_sec) / (abs(alpha_v) * self.system.l_tot))
        return max(min(candidates), 0.0) if candidates else float("inf")

    def calc_shear_prestress_deviation_force(self):
        if not hasattr(self.section, "calc_prestress_shear_deviation_force"):
            return 0.0
        direction = "x" if self.li_max == self.system.lx else "y"
        return self.section.calc_prestress_shear_deviation_force(direction)

    def calc_shear_secondary_force(self, index=0):
        if not hasattr(self.section, "get_secondaryInternalForces"):
            return 0.0
        _, _, v_sec = self.section.get_secondaryInternalForces(self.system)
        if not v_sec:
            return 0.0
        return v_sec[min(index, len(v_sec) - 1)]

    def calc_punching_qu(self):
        if not hasattr(self.section, "calc_punching_shear_resistance"):
            return float("inf")
        m_rd = self.calc_punching_m_rd()
        area = self.system.column_tributary_area
        secondary_forces = None
        if hasattr(self.section, "get_secondaryInternalForces"):
            secondary_forces = self.section.get_secondaryInternalForces(self.system)
        v_sec = self.calc_punching_secondary_force(secondary_forces)

        def residual(q_area):
            m_ed = self.calc_punching_m_ed(q_area, secondary_forces)
            v_rd = self.section.calc_punching_shear_resistance(
                column_width=self.system.column_width,
                column_length=self.system.column_length,
                ke=self.system.column_ke,
                l_x=self.system.lx,
                l_y=self.system.ly,
                m_ed=m_ed,
                m_rd=m_rd,
            )
            return v_rd / area - (q_area + v_sec / area)

        q_low = 0.0
        q_high = max(self.qu, 1.0)
        while residual(q_high) > 0 and q_high < 1e7:
            q_high *= 2
        for _ in range(40):
            q_mid = 0.5 * (q_low + q_high)
            if residual(q_mid) >= 0:
                q_low = q_mid
            else:
                q_high = q_mid
        return q_low

    def calc_punching_m_ed(self, q_area, secondary_forces=None):
        alpha_m_x, alpha_m_y = self.uls_redistributed_moment_factors()
        moments_x = [
            q_area * alpha_m_x[0] * self.system.l_tot ** 2,
            q_area * alpha_m_x[1] * self.system.l_tot ** 2,
        ]
        moments_y = [
            q_area * alpha_m_y[0] * self.li_min ** 2,
            q_area * alpha_m_y[1] * self.li_min ** 2,
        ]
        if hasattr(self.section, "get_secondaryInternalForces"):
            if secondary_forces is None:
                secondary_forces = self.section.get_secondaryInternalForces(self.system)
            m_sec_x, m_sec_y, _ = secondary_forces
            moments_x[0] += m_sec_x[0]
            moments_x[1] += m_sec_x[1]
            moments_y[0] += m_sec_y[0]
            moments_y[1] += m_sec_y[1]
        return max(abs(m) for m in moments_x), max(abs(m) for m in moments_y)

    def calc_punching_m_rd(self):
        m_rd_x = max(abs(self.section.mu_max), abs(self.section.mu_min), abs(getattr(self.section, "m_r", 0)), 1e-9)
        m_rd_y = m_rd_x
        return m_rd_x, m_rd_y

    def calc_punching_secondary_force(self, secondary_forces=None):
        if not hasattr(self.section, "get_secondaryInternalForces"):
            return 0.0
        if secondary_forces is None:
            secondary_forces = self.section.get_secondaryInternalForces(self.system)
        _, _, v_sec = secondary_forces
        if not v_sec:
            return 0.0
        d_v = getattr(self.section, "d", 0.0)
        control_width_x = self.system.column_width + 2 * d_v
        control_width_y = self.system.column_length + 2 * d_v
        return v_sec[0] * control_width_y + v_sec[min(1, len(v_sec) - 1)] * control_width_x

    def calc_punching_resistance_for_current_loads(self):
        if not hasattr(self.section, "calc_punching_shear_resistance"):
            return float("inf")
        m_ed = self.calc_punching_m_ed(self.qu)
        m_rd = self.calc_punching_m_rd()
        v_rd = self.section.calc_punching_shear_resistance(
            column_width=self.system.column_width,
            column_length=self.system.column_length,
            ke=self.system.column_ke,
            l_x=self.system.lx,
            l_y=self.system.ly,
            m_ed=m_ed,
            m_rd=m_rd,
        )
        return v_rd / self.system.column_tributary_area

    def calc_required_punching_shear_reinforcement_resistance(self, q_area=None):
        if not getattr(self.system, "has_columns", False):
            return 0.0
        if not hasattr(self.section, "calc_punching_shear_resistance"):
            return 0.0
        q_area = self.load_combinations.uls() if q_area is None else q_area
        secondary_forces = None
        if hasattr(self.section, "get_secondaryInternalForces"):
            secondary_forces = self.section.get_secondaryInternalForces(self.system)
        v_sec = self.calc_punching_secondary_force(secondary_forces)
        v_ed = q_area * self.system.column_tributary_area + v_sec
        m_ed = self.calc_punching_m_ed(q_area, secondary_forces)
        m_rd = self.calc_punching_m_rd()
        original_bw_bg = getattr(self.section, "bw_bg", None)
        try:
            if original_bw_bg is not None:
                self.section.bw_bg = (0.0, original_bw_bg[1], 0)
            v_rd_without_s = self.section.calc_punching_shear_resistance(
                column_width=self.system.column_width,
                column_length=self.system.column_length,
                ke=self.system.column_ke,
                l_x=self.system.lx,
                l_y=self.system.ly,
                m_ed=m_ed,
                m_rd=m_rd,
            )
        finally:
            if original_bw_bg is not None:
                self.section.bw_bg = original_bw_bg
        punching_deficit = max(v_ed - v_rd_without_s, 0.0)
        # SIA 262 punching reinforcement: once punching reinforcement is
        # required, use at least Vd/2 as minimum reinforcement resistance.
        self.punching_vrds_required = max(punching_deficit, 0.5 * v_ed) if punching_deficit > 0.0 else 0.0
        return self.punching_vrds_required

    def apply_required_punching_reinforcement(self, q_area=None):
        section = self.section
        if (
            getattr(section, "section_type", "") not in ("rc_rec", "pc_rec")
            or not self.should_check_punching()
        ):
            volume = 0.0
            a_ds_req = 0.0
            v_rd_s_req = 0.0
        else:
            v_rd_s_req = self.calc_required_punching_shear_reinforcement_resistance(q_area)
            ke = max(float(getattr(self.system, "column_ke", 1.0) or 1.0), 1e-9)
            a_ds_req = max(v_rd_s_req, 0.0) / max(ke * section.rebar_type.fsd, 1e-9)
            tributary_area = max(self.system.lx * self.system.ly, 1e-9)
            joint_surcharge = max(float(getattr(section, "joint_surcharge", 0.0) or 0.0), 0.0)
            volume = a_ds_req / tributary_area * (1.0 + joint_surcharge)

        section.set_punching_reinforcement_volume(volume)
        self.punching_a_ds_req_m2 = a_ds_req
        self.punching_steel_volume_m3_m2 = volume
        self.shear_reinforcement_volume_m3_m2 = 0.0
        self.punching_steel_additional_volume_m3_m2 = volume
        self.punching_steel_co2_kgCO2eq_m2 = section.punching_steel_co2
        self.punching_steel_cost_CHF_m2 = section.punching_steel_cost
        self.punching_steel_time_h_m2 = section.punching_steel_construction_time
        self.punching_steel_additional_co2_kgCO2eq_m2 = section.punching_steel_co2
        self.punching_steel_additional_cost_CHF_m2 = section.punching_steel_cost
        self.punching_steel_additional_time_h_m2 = section.punching_steel_construction_time
        self.punching_V_Rd_s_required_N = v_rd_s_req
        return volume

    def calc_qk_zul_gzt(self, gamma_g=1.35, gamma_q=1.5):
        self.qu = self.calc_qu()
        self.qk_zul_gzt = max((self.qu - gamma_g * self.gk) / gamma_q, 0)
        qu_bending = getattr(self, "qu_bending", float("nan"))
        qu_shear = getattr(self, "qu_shear", float("nan"))
        self.qk_zul_bending_gzt = (
            max((qu_bending - gamma_g * self.gk) / gamma_q, 0)
            if np.isfinite(qu_bending)
            else float("inf")
        )
        self.qk_zul_shear_gzt = (
            max((qu_shear - gamma_g * self.gk) / gamma_q, 0)
            if np.isfinite(qu_shear)
            else float("inf")
        )

    def calc_f1(self):
        # calculates first frequency of system according to HBT, Seite 46
        kf2 = self.system.kf2
        l_rech = self.system.li_max
        section_material = self.section.section_type[0:2]
        if section_material in ("rc", "pc"):  # take cracked stiffness for concrete sections if section is cracked
            if concrete_member_is_uncracked(self):
                eil = self.section.ei1
            else:
                eil = self.section.ei2
        else:
            eil = self.section.ei1
        m = self.m
 #       print("m =", m)
        nu_c = 0.2 # Poisson's ratio for concrete, used for correction of frequency according to SIA 262
        f1 = kf2 / (2*np.pi*l_rech**2)* (abs(eil) / (abs(m)*(1-nu_c**2)))**0.5 #eigenfrequency for slabs according to ZC1 Grundlagen Baudynamik
        return f1

    def calc_vib1(self, f0=700):
        # calculates a_Ed according to HBT, Seite 47
        f1 = self.f1
        if f1 <= 1e-9:
            return float("inf")
        m_gen = self.m * self.system.li_max / 2 * self.bm_rech
        xi = self.section.xi
        if f1 <= 5.1:
            alpha = 0.2
            ff = f1
        elif f1 <= 6.9:
            alpha = 0.06
            ff = f1
        else:
            alpha = 0.06
            ff = 6.9
        a_ed = 0.4 * f0 * alpha / m_gen * 1 / (((f1 / ff) ** 2 - 1) ** 2 + (2 * xi * f1 / ff) ** 2) ** 0.5  # HBT, Seite 47
        return a_ed

    def calc_vib2(self, f=1000):
        # calculates W_F,ED according to to HBT, Seite 48 (alpha_w_f_cd is approximated from simple span beam to slab within class slab)
        wf_ed = self.system.alpha_w_f_cd * f * self.system.li_max ** 3 / (self.bm_rech * self.section.ei1)
        section_material = self.section.section_type[0:2]
        if section_material in ("rc", "pc"):  # take cracked stiffness for calculation of concrete sections
            eil = self.section.ei2
        else:
            eil = self.section.ei1
        ve_ed = 364 / (abs(self.bm_rech) * (abs(self.m) ** 3 * abs(eil) * 1e6) ** 0.25)
        return wf_ed, ve_ed

    def get_fire_resistance(self):
        # evaluate fire resistance
        if self.section.section_type == "rc_rec":
            fire_resistance = RectangularConcrete.fire_resistance(self.section)
        elif self.section.section_type == "pc_rec":
            fire_resistance = PostTensionedConcrete.fire_resistance(self.section)
        # elif self.section.section_type == "wd_rec":
        #     fire_resistance = RectangularWood.fire_resistance(self)
        # elif self.section.section_type == "rc_rib":
        #     fire_resistance = RibbedConcrete.fire_resistance(self.section)
        # elif self.section.section_type == "wd_rib":
        #     fire_resistance = RibWood.fire_resistance(self.section)
        else:
            #print("fire resistance for is not defined for that cross-section type.")
            fire_resistance = None
        self.fire_resistance = fire_resistance


class Requirements:
    def __init__(self, install="ductile", lw_install=350, lw_use=350, lw_app=300, f1=8, a_cd=0.1, w_f_cdr1=1.0e-3,
                 alpha_ve_cd=1 / 3, fire='R60', acoustic_level="normal"):
        self.install = install
        self.lw_install = lw_install  # preset value: SIA 260
        self.lw_use = lw_use  # preset value: SIA 260
        self.lw_app = lw_app  # preset value: SIA 260
        self.f1 = f1  # preset value: HBT, Seite 46
        self.a_cd = a_cd  # preset value: HBT, Seite 46
        self.w_f_cdr1 = w_f_cdr1  # preset value: HBT, Seite 48
        self.alpha_ve_cd = alpha_ve_cd  # preset value: HBT, Seite 49
        self.t_fire = int(fire[1:])  # unit: [min]
        self.acoustic = AcousticRequirements(acoustic_level)

class AcousticRequirements:
    def __init__(self, level="normal"):
        if level not in ("normal", "increased"):
            raise ValueError("Acoustic requirement level has to be 'normal' or 'increased'.")
        self.level = level
        if level == "normal":
            self.rw_min = 53.0
            self.lnw_max = 51.0
        else:
            self.rw_min = 57.0
            self.lnw_max = 47.0
