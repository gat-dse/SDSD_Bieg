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
# create database connection
weights = sqlite3.connect("MIVES_260424.db")
# write data to database
df_weights.to_sql("Balanced", weights, if_exists="replace", index=False)


class MIVESEvaluator:
    def __init__(self, weights=df_weights):
        # Read weights from the database
        self.weights = {
        }

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
    
        # Sicherstellen, dass x innerhalb der Grenzen liegt
        if x_min < x_max: # Fall: Höherer Wert ist besser (z.B. Lebensdauer)
            if x <= x_min: return 0.0
            if x >= x_max: return 1.0
        else: # Fall: Niedrigerer Wert ist besser (z.B. CO2, Kosten)
            if x >= x_min: return 0.0
            if x <= x_max: return 1.0

        # Faktor B berechnen, um den Bereich auf (0, 1) zu normieren
        # B = 1 / (1 - exp(-k * (|x_max - x_min| / c)^p))
        diff_max = abs(x_max - x_min)
        b = 1 / (1 - np.exp(-k * (diff_max / c)**p))
        
        # Die eigentliche Wertfunktion Vi
        diff_x = abs(x - x_min)
        v_i = b * (1 - np.exp(-k * (diff_x / c)**p))
    
        return v_i

    def evaluate_slab(self, data):
        """
        data: Dictionary mit berechneten Werten aus deinem Statik-Tool
        """
        # 1. Ökologie: CO2-Emissionen (GWP)
        # x_min = 20kg/m2 (Ziel), x_max = 60kg/m2 (Schlecht)
        v_eco = self.value_function(data['gwp'], 20, 60, 25, 1, 1.5)
        
        # 2. Ökonomie: Material- und Baukosten
        # x_min = 50€/m2, x_max = 120€/m2
        v_cost = self.value_function(data['cost'], 50, 120, 30, 1, 1.2)
        
        # 3. Soziales: Flexibilität (z.B. große Spannweiten / Dual-Banded Vorteil)
        # x_min = 5m Spannweite, x_max = 12m Spannweite
        v_social = self.value_function(data['span_length'], 5, 12, 8, 2, 2)
        
        # Gesamtindex S
        S = (v_eco * self.weights['ecology'] + 
             v_cost * self.weights['economy'] + 
             v_social * self.weights['social'])
        
        return {
            'Total_Sustainability_Index': S,
            'Ecology_Score': v_eco,
            'Economy_Score': v_cost,
            'Social_Score': v_social
        }

# --- Beispielanwendung in deinem Tool ---
# Werte kommen aus deiner Statik-Berechnung (Betonvolumen, Stahlgewicht, PT-Litzen)
pt_slab_results = {
    'gwp': 35.5,    # kg CO2/m2
    'cost': 85.0,   # €/m2
    'span_length': 10.0 # Meter
}

evaluator = MIVESEvaluator()
score = evaluator.evaluate_slab(pt_slab_results)

print(f"MIVES Nachhaltigkeitsindex: {score['Total_Sustainability_Index']:.2f}")