"""Input definition for the final slab-system comparison.

The file mirrors the methodology slides:
- one shared slab configurator setup,
- one residential use case,
- one office use case,
- several slab systems per use case.

Keep this file as the place where spans, loads, floor build-ups, systems and
material groups are changed for the final comparison.
"""

DATABASE_NAME = "database_260126.db"
OUTPUT_DIR = "plots"

CRITERIA = ["ENV"]
OPTIMA = ["GWP"]
MAX_ITER = 100
G2K = 0.75e3
VERIFICATION_INDEX = 1
FIRE_BOTTOM = [1, 0, 0, 0]
FIRE_BOTTOM_AND_SIDES = [1, 1, 0, 1]

AUTO_FLOOR_BUILDUP = True
ACOUSTIC_LEVEL = "normal"

# The dataset functions still need an initial floor object. With AUTO_FLOOR_BUILDUP
# enabled, this placeholder is replaced by AcousticFloorGenerator for each section.
BASE_FLOOR_BUILDUP = [
    ["'Parkett 2-Schicht werkversiegelt, 11 mm'", False, False],
]

MATERIAL_GROUPS = {
    "concrete": ["'ready_mixed_concrete'"],
    "timber": ["'Glue_laminated_timber'"],
    "tcc": [("'ready_mixed_concrete'", "'Glue_laminated_timber'", "'kerve'")],
}

SCENARIOS = {
    "residential": {
        "label": "Residential",
        # Use span values available in slab_properties.db for the 2D systems.
        "lengths": [3, 5, 6, 7, 8, 10],
        "qk": 2.0e3,
        "systems": [
            {
                "id": "res_rc_flat_walls",
                "label": "Rectangular concrete",
                "dimension": "2D",
                "crsec_type": "rc_rec",
                "materials": "concrete",
                "structural_system": "2-way, full continuity, walls",
                "slab_support": "LL-eingespannt",
                "enabled": True,
            },
            {
                "id": "res_pt_flat_walls",
                "label": "Rectangular concrete PT",
                "dimension": "2D",
                "crsec_type": "pc_rec",
                "materials": "concrete",
                "pt_layout": [1, 0, 1, 0],
                "structural_system": "2-way, full continuity, walls",
                "slab_support": "LL-eingespannt",
                "enabled": True,
            },
            {
                "id": "res_wood_flat_simple",
                "label": "Rectangular wood",
                "dimension": "1D",
                "crsec_type": "wd_rec",
                "materials": "timber",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM,
                "enabled": True,
            },
            {
                "id": "res_tcc_flat_notches",
                "label": "TCC, flat, notches",
                "dimension": "1D",
                "crsec_type": "tcc",
                "materials": "tcc",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM,
                "enabled": True,
            },
            {
                "id": "res_tcc_ribs_screws",
                "label": "TCC, ribs, screws",
                "dimension": "1D",
                "crsec_type": "tcc",
                "materials": "tcc",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
                "enabled": False,
                "note": "Use when the ribbed TCC geometry is represented separately from the current TCC input.",
            },
            {
                "id": "res_hollow_core_simple",
                "label": "Hollow core",
                "dimension": "1D",
                "crsec_type": "wd_rib",
                "materials": "timber",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
                "enabled": True,
            },
        ],
    },
    "office": {
        "label": "Office",
        # Use span values available in slab_properties.db for the 2D systems.
        "lengths": [8, 10, 12, 16],
        "qk": 3.0e3,
        "systems": [
            {
                "id": "off_rc_flat_columns",
                "label": "Rectangular concrete",
                "dimension": "2D",
                "crsec_type": "rc_rec",
                "materials": "concrete",
                "structural_system": "2-way, full continuity, columns",
                "slab_support": "PL-eingespannt",
                "enabled": True,
            },
            {
                "id": "off_pt_flat_columns_banded",
                "label": "Rectangular concrete PT band.",
                "dimension": "2D",
                "crsec_type": "pc_rec",
                "materials": "concrete",
                "pt_layout": [1, 0, 1, 0],
                "structural_system": "2-way, full continuity, columns",
                "slab_support": "PL-eingespannt",
                "enabled": True,
            },
            {
                "id": "off_pt_flat_columns_distributed",
                "label": "Rectangular concrete PT dist.",
                "dimension": "2D",
                "crsec_type": "pc_rec",
                "materials": "concrete",
                "pt_layout": [0, 1, 0, 1],
                "structural_system": "2-way, full continuity, columns",
                "slab_support": "PL-eingespannt",
                "enabled": True,
            },
            {
                "id": "off_ribbed_concrete_continuous",
                "label": "Ribbed concrete",
                "dimension": "1D",
                "crsec_type": "rc_rib",
                "materials": "concrete",
                "structural_system": "Continuous beam",
                "system_type": "continuous_elastic",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
                "enabled": True,
            },
            {
                "id": "off_tcc_ribs_screws",
                "label": "TCC, ribs, screws",
                "dimension": "1D",
                "crsec_type": "tcc",
                "materials": "tcc",
                "structural_system": "Simple span",
                "system_type": "simple_span",
                "fire_array": FIRE_BOTTOM_AND_SIDES,
                "enabled": True,
            },
        ],
    },
}
