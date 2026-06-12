import pytest

import struct_analysis


@pytest.fixture(scope="module")
def tcc_materials():
    database_name = "database_260126.db"
    concrete = struct_analysis.ReadyMixedConcrete("'C25/30'", database_name)
    concrete.get_design_values()
    rebar = struct_analysis.SteelReinforcingBar("'B500B'", database_name)
    rebar.get_design_values()
    timber = struct_analysis.Wood("'GL24h'", database_name)
    timber.get_design_values()
    connector = struct_analysis.ConnectorTCC("'DBS_10'", database_name)
    return concrete, rebar, timber, connector


def make_tcc(materials, h_c):
    concrete, rebar, timber, connector = materials
    return struct_analysis.TCC(
        concrete,
        rebar,
        timber,
        connector,
        0.06,
        0.625,
        h_c,
        0.40,
        0.18,
        0.02,
        10.0,
    )


def test_tcc_uses_two_reinforcement_layers_for_all_topping_depths(tcc_materials):
    thin = make_tcc(tcc_materials, 0.10)
    thick = make_tcc(tcc_materials, 0.18)

    assert thin.rebar_layers == 2
    assert thick.rebar_layers == 2
    assert thick.as_rebar == pytest.approx(thin.as_rebar)
