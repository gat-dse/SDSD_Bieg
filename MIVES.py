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
        self.weights = weights['Wt (%)']/100  # Convert percentage to decimal
        self.members_data = []
        for member in members:
            member_data = {
            'cost': self.getCost(member),  # CHF/m2
            'construction_time': self.getConstructionTime(member),  # h/m2
            'co2': self.getCO2(member),  # kg CO2/m2
            'h_tot': self.geth_tot(member),  # m           
            'weight': self.getWeight(member),  # N/m2
            }
            self.members_data.append(member_data)

    def getCost(self, member):
        cost = 0
        cost += member.floorstruc.cost # Floor structure cost
        cost += member.section.cost # Section cost
        return cost
    
    def getConstructionTime(self, member):
        time = 0
        time += member.floorstruc.construction_time
        time += member.section.construction_time
        return time
    
    def getCO2(self, member):
        co2 = 0
        co2 += member.floorstruc.co2
        co2 += member.section.co2
        return co2
    
    def getWeight(self, member):
        weight = 0
        weight += member.floorstruc.gk_area
        weight += member.section.w
        return weight
    
    def geth_tot(self, member):
        h_tot = 0
        h_tot += member.floorstruc.h
        h_tot += member.section.h
        return h_tot

    def mives_value_function(self, x, x_min, x_max, c, k, p):
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
        costs = [member['cost'] for member in self.members_data]
        x_min_cost = max(costs) # higher cost = worse, so max cost is the min value for the value function
        x_max_cost = min(costs)
        c_cost = abs(x_max_cost - x_min_cost)
        k_cost = 0.01  # nearly linear
        p_cost = 1  # linear

        # I2: Construction Time - linear
        times = [member['construction_time'] for member in self.members_data]
        x_min_time = max(times) # higher time = worse, so max time is the min value for the value function
        x_max_time = min(times)
        c_time = abs(x_max_time - x_min_time)
        k_time = 0.01  # nearly linear
        p_time = 1

        # I3: CO2 Emissions - linear
        co2_values = [member['co2'] for member in self.members_data]
        x_min_co2 = max(co2_values) # higher CO2 = worse, so max CO2 is the min value for the value function
        x_max_co2 = min(co2_values)
        c_co2 = abs(x_max_co2 - x_min_co2)
        k_co2 = 0.01
        p_co2 = 1

        # I4: Total Height - linear
        heights = [member['h_tot'] for member in self.members_data]
        x_min_h_tot = max(heights) # higher height = worse, so max height is the min value for the value function
        x_max_h_tot = min(heights)
        c_h_tot = abs(x_max_h_tot - x_min_h_tot)
        k_h_tot = 0.01
        p_h_tot = 1

        # I5: Weight - linear
        weights = [member['weight'] for member in self.members_data]
        x_min_weight = max(weights) # higher weight = worse, so max weight is the min value for the value function
        x_max_weight = min(weights)
        c_weight = abs(x_max_weight - x_min_weight)
        k_weight = 0.01
        p_weight = 1


        # Evaluate value functions for each member and each indicator
        v_cost = [self.mives_value_function(cost, x_min_cost, x_max_cost, c_cost, k_cost, p_cost) for cost in costs]
        v_time = [self.mives_value_function(time, x_min_time, x_max_time, c_time, k_time, p_time) for time in times]
        v_co2 = [self.mives_value_function(co2, x_min_co2, x_max_co2, c_co2, k_co2, p_co2) for co2 in co2_values]
        v_h_tot = [self.mives_value_function(height, x_min_h_tot, x_max_h_tot, c_h_tot, k_h_tot, p_h_tot) for height in heights]
        v_weight = [self.mives_value_function(weight, x_min_weight, x_max_weight, c_weight, k_weight, p_weight) for weight in weights]

        # Calculate scores for each member
        scores = []
        for i in range(len(self.members_data)):
            # Ecology Score (I3, I4, I5)
            v_eco = self.weights[2] * v_co2[i] + self.weights[3] * v_h_tot[i] + self.weights[4] * v_weight[i]
            # Economy Score (I1, I2)
            v_cost_score = self.weights[0] * v_cost[i] + self.weights[1] * v_time[i]
            # Total Sustainability Index
            S = v_eco + v_cost_score 
            scores.append((S, v_eco, v_cost_score))

        return scores
    