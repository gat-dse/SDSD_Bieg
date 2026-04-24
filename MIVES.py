# Calculations for the MIVES dimensionless cost function

import struct_analysis
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

# Import weights
excel_file = "/Users/jonathanbieg/Documents/Master Thesis/1_Code/Python Repository/SDSD_Bieg/Database/260424_MIVES_weights.xlsx"  
# read excel
df_weights= pd.read_excel(excel_file, sheet_name="Balanced", engine="openpyxl") # Scenario "Balanced"
df_input = pd.read_excel(excel_file, sheet_name="Input", engine="openpyxl") # Input values for MIVES cost evaluation
# create database connection
conn = sqlite3.connect("MIVES_260424.db")
# write data to database
df_weights.to_sql("Balanced", conn, if_exists="replace", index=False)
df_input.to_sql("Input", conn, if_exists="replace", index=False)

#Check if data is written correctly
#print(df_weights.head())
#print(df_input.head())

class MIVESEvaluator:
    def __init__(self, members, weights = df_weights):
        # Read weights from the database
        self.weights = weights['Wt (%)']
        self.members_data = []
        for member in members:
            member_data = {
            'cost': self.getCost(member),  # CHF/m2
            'construction_time': self.getConstructionTime(member),  # h/m2
            'co2': self.getCO2(member),  # kg CO2/m2
            'h_tot': self.geth_tot(member),  # m           
            'weight': self.getWeight(member),  # N/m2
            'h_installation': member.section.h_installation  # m
            }
            self.members_data.append(member_data)

    def getCost(member):
        cost = 0
        cost += member.floor_structure.cost # Floor structure cost
        cost += member.section.cost # Section cost
        return cost
    
    def getConstructionTime(member):
        time = 0
        time += member.floor_structure.construction_time
        time += member.section.construction_time
        return time
    
    def getCO2(member):
        co2 = 0
        co2 += member.floor_structure.co2
        co2 += member.section.co2
        return co2
    
    def getWeight(member):
        weight = 0
        weight += member.floor_structure.gk_area
        weight += member.section.w
        return weight
    
    def geth_tot(member):
        h_tot = 0
        h_tot += member.floor_structure.h
        h_tot += member.section.h
        return h_tot

    def mives_value_function(x, x_min, x_max, c, k, p):
        """
        Implementierung der MIVES Wertfunktion nach der Formel:
        Vi = B * (1 - exp(-k * (|x - x_min| / c)^p))
        
        Parameter:
        x    : Aktueller Wert des Indikators
        x_min: Untergrenze (Wert = 0)
        x_max: Obergrenze (Wert = 1)
        c    : Annäherung an den Wendepunkt
        k    : Wert am Wendepunkt (Skalierungsfaktor)
        p    : Formfaktor (p < 1 konkav, p = 1 linear, p > 1 konvex/S)
        """

        # Faktor B berechnen, um den Bereich auf (0, 1) zu normieren
        # B = 1 / (1 - exp(-k * (|x_max - x_min| / c)^p))
        diff_max = abs(x_max - x_min)
        b = 1 / (1 - np.exp(-k * (diff_max / c)**p))
        
        # Die eigentliche Wertfunktion Vi
        diff_x = abs(x - x_min)
        v_i = b * (1 - np.exp(-k * (diff_x / c)**p))
    
        return v_i

    def evaluate(self):
        # I1: Cost - linear
        x_min_cost = self.members_data['cost'].min()
        x_max_cost = self.members_data['cost'].max()
        c_cost = abs(x_max_cost - x_min_cost)
        k_cost = 0.01  #nearly linear
        p_cost = 1 # linear
                
        # I2: Construction Time - linear
        x_min_time = self.members_data['construction_time'].min()
        x_max_time = self.members_data['construction_time'].max()
        c_time = abs(x_max_time - x_min_time)
        k_time = 0.01  #nearly linear
        p_time = 1

        # I3: CO2 Emissions - linear
        x_min_co2 = self.members_data['co2'].min()
        x_max_co2 = self.members_data['co2'].max()
        c_co2 = abs(x_max_co2 - x_min_co2)
        k_co2 = 0.01
        p_co2 = 1

        # I4: Total Height - linear
        x_min_h_tot = self.members_data['h_tot'].min()
        x_max_h_tot = self.members_data['h_tot'].max()
        c_h_tot = abs(x_max_h_tot - x_min_h_tot)
        k_h_tot = 0.01
        p_h_tot = 1

        # I5: Weight - linear
        x_min_weight = self.members_data['weight'].min()
        x_max_weight = self.members_data['weight'].max()
        c_weight = abs(x_max_weight - x_min_weight)
        k_weight = 0.01
        p_weight = 1

        # I6: Installation Height - linear
        x_min_h_installation = self.members_data['h_installation'].min()
        x_max_h_installation = self.members_data['h_installation'].max()
        c_h_installation = abs(x_max_h_installation - x_min_h_installation)
        k_h_installation = 0.01
        p_h_installation = 1

        # Evaluate value functions for each member and each indicator
        # Continue here 
        
        # Ecology Score (I3, I4, I5)
        v_eco = self.weights[2] * v_co2 + self.weights[3] * v_h_tot + self.weights[4] * v_weight
        # Economy Score (I1, I2)
        v_cost = self.weights[0] * v_cost + self.weights[1] * v_time
        # Social Score (I6)
        v_social = self.weights[5] * v_h_installation
        # Total Sustainability Index
        S = v_eco + v_cost + v_social
        
        return S, v_eco, v_cost, v_social
