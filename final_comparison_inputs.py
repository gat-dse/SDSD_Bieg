"""Input definition for the final slab-system comparison.

The final comparison contains two use cases:
- Residential: qk = 2 kN/m2, spans 3-10 m
- Office: qk = 3 kN/m2, spans 8-16 m

The runner uses these inputs to create:
- one single-system plot per system with ULS, SLS1, SLS2 and FIRE
- one ENV comparison plot per use case with structural and total values
"""

DATABASE_NAME = "database_260126.db"
OUTPUT_DIR = "plots"

DESIGN_CRITERIA = ["ULS", "SLS1", "SLS2", "FIRE"]
ENV_CRITERIA = ["ENV"]
OPTIMA = ["GWP"]
MAX_ITER = 150
G2K = 0.75e3
VERIFICATION_INDEX = 1

FIRE_BOTTOM = [1, 0, 0, 0]
FIRE_BOTTOM_AND_SIDES = [1, 1, 0, 1]

AUTO_FLOOR_BUILDUP = True
ACOUSTIC_LEVEL = "normal"

# The dataset functions require an initial floor object. With AUTO_FLOOR_BUILDUP
# enabled this placeholder is replaced by AcousticFloorGenerator for every
# optimized cross-section.
BASE_FLOOR_BUILDUP = [
    ["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
]

MATERIAL_GROUPS = {
    "concrete": ["'ready_mixed_concrete'"],
    "timber": ["'Glue_laminated_timber'", "'Solid_structural_timber'"],
    "tcc_kerve": [("'ready_mixed_concrete'", "'Glue_laminated_timber'", "'kerve'")],
    "tcc_dbs": [("'ready_mixed_concrete'", "'Glue_laminated_timber'", "'DBS_10'")],
}

TCC_FLAT_KERVE = {
    "s": 0.50,
    "a_ribs": 1.00,
    "h_c": 0.08,
    "h_w": 0.12,
    "b_w": 1.00,
    "d": 0.0,
    "l0": 2.0,
}

TCC_RIBS_DBS = {
    "s": 0.15,
    "a_ribs": 0.625,
    "h_c": 0.08,
    "h_w": 0.12,
    "b_w": 0.18,
    "d": 0.0,
    "l0": 2.0,
}

TCC_RIBS_DBS_OFFICE = {
    **TCC_RIBS_DBS,
    "b_w": 0.24,
}

SCENARIOS = {
    "residential": {
        "label": "Residential",
        "lengths": [3, 5, 6, 7, 8, 10],
        "span_range": "3, 5, 6, 7, 8, 10 m",
        "qk": 2.0e3,
        "systems": [
            {
                "id": "res_rc_flat_walls",
                "label": "Rectangular concrete",
                "dimension": "2D",
                "crsec_type": "rc_rec",
                "materials": "concrete",
                "description": "conventionally reinforced",
                "structural_system": "2-way, full continuity, walls",
                "slab_support": "LL-eingespannt",
            },
            {
                "id": "res_pt_flat_walls_dist",
                "label": "Rectangular concrete PT dist.",
                "dimension": "2D",
                "crsec_type": "pc_rec",
                "materials": "concrete",
                "description": "post-tensioned, distributed layout",
                "pt_layout": [0, 1, 0, 1],
                "structural_system": "2-way, full continuity, walls",
                "slab_support": "LL-eingespannt",
            },
            {
                "id": "res_wood_flat_simple",
                "label": "Rectangular wood",
                "dimension": "1D",
                "crsec_type": "wd_rec",
                "materials": "timber",
                "description": "BSH",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM,
            },
            {
                "id": "res_tcc_flat_kerve",
                "label": "TCC flat, kerve",
                "dimension": "1D",
                "crsec_type": "tcc",
                "materials": "tcc_kerve",
                "description": "BSH, connection: kerve, s=0.5 m",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM,
                "section_params": TCC_FLAT_KERVE,
            },
            {
                "id": "res_tcc_ribs_dbs",
                "label": "TCC ribs, DBS",
                "dimension": "1D",
                "crsec_type": "tcc",
                "materials": "tcc_dbs",
                "description": "Ribs, connection: DBS_10, s=0.15 m, a_ribs=0.625 m, b_w=0.18 m",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
                "section_params": TCC_RIBS_DBS,
            },
            {
                "id": "res_hollow_core_simple",
                "label": "Ribbed timber hollow core",
                "dimension": "1D",
                "crsec_type": "wd_rib",
                "materials": "timber",
                "description": "Hollow core",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
            },
        ],
    },
    "office": {
        "label": "Office",
        "lengths": [8, 10, 12, 16],
        "span_range": "8, 10, 12, 16 m",
        "qk": 3.0e3,
        "systems": [
            {
                "id": "off_rc_flat_columns",
                "label": "Rectangular concrete",
                "dimension": "2D",
                "crsec_type": "rc_rec",
                "materials": "concrete",
                "description": "conventionally reinforced",
                "structural_system": "2-way, full continuity, columns",
                "slab_support": "PL-eingespannt",
            },
            {
                "id": "off_pt_flat_columns_dist",
                "label": "Rectangular concrete PT dist.",
                "dimension": "2D",
                "crsec_type": "pc_rec",
                "materials": "concrete",
                "description": "post-tensioned, distributed layout",
                "pt_layout": [0, 1, 0, 1],
                "structural_system": "2-way, full continuity, columns",
                "slab_support": "PL-eingespannt",
            },
            {
                "id": "off_pt_flat_columns_band",
                "label": "Rectangular concrete PT band.",
                "dimension": "2D",
                "crsec_type": "pc_rec",
                "materials": "concrete",
                "description": "post-tensioned, banded layout",
                "pt_layout": [1, 0, 1, 0],
                "structural_system": "2-way, full continuity, columns",
                "slab_support": "PL-eingespannt",
            },
            {
                "id": "off_ribbed_concrete_continuous",
                "label": "Ribbed concrete",
                "dimension": "1D",
                "crsec_type": "rc_rib",
                "materials": "concrete",
                "description": "conventionally reinforced",
                "structural_system": "Continuous beam",
                "system_type": "continuous_elastic",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
            },
            {
                "id": "off_tcc_ribs_dbs",
                "label": "TCC ribs, DBS",
                "dimension": "1D",
                "crsec_type": "tcc",
                "materials": "tcc_dbs",
                "description": "Ribs, connection: DBS_10, s=0.15 m, a_ribs=0.625 m, b_w=0.24 m",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
                "section_params": TCC_RIBS_DBS_OFFICE,
            },
        ],
    },
}
