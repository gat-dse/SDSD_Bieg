from types import SimpleNamespace

import pytest

import struct_analysis
import struct_optimization_2D


def concrete_member(mkd_p, mkd_n, mkd_p_y=None, mkd_n_y=None):
    member = SimpleNamespace(
        section=SimpleNamespace(mr_p=100.0, mr_n=-100.0),
        mkd_p=mkd_p,
        mkd_n=mkd_n,
    )
    if mkd_p_y is not None:
        member.mkd_p_y = mkd_p_y
        member.mkd_n_y = mkd_n_y
    return member


def test_concrete_cracking_check_uses_signed_positive_and_negative_moments():
    assert struct_analysis.concrete_member_is_uncracked(concrete_member(80.0, -90.0))
    assert not struct_analysis.concrete_member_is_uncracked(concrete_member(110.0, -90.0))
    assert not struct_analysis.concrete_member_is_uncracked(concrete_member(80.0, -110.0))


def test_concrete_cracking_check_includes_second_slab_direction():
    member = concrete_member(80.0, -90.0, mkd_p_y=120.0, mkd_n_y=-90.0)
    assert not struct_analysis.concrete_member_is_uncracked(member)


def test_sls1_penalty_uses_cracked_deflection_after_cracking():
    member = concrete_member(110.0, -90.0)
    member.w_install = member.w_use = member.w_app = 0.001
    member.w_install_ger = 0.020
    member.w_use_ger = 0.015
    member.w_app_ger = 0.025
    member.w_install_adm = member.w_use_adm = member.w_app_adm = 0.010

    penalty = struct_optimization_2D.calc_sls1_penalty(member)

    assert penalty == pytest.approx(1500.0)


def test_standalone_sls1_allows_uls_infeasible_member():
    member = concrete_member(80.0, -90.0)
    member.qk = 3000.0
    member.qk_zul_gzt = 0.0
    member.w_install = member.w_use = member.w_app = 0.0
    member.w_install_ger = member.w_use_ger = member.w_app_ger = 0.0
    member.w_install_adm = member.w_use_adm = member.w_app_adm = 0.010

    penalty = struct_optimization_2D.criterion_penalty(member, "SLS1", include_uls_guard=False)

    assert penalty == 0.0


def vibration_member(f1, a_ed, wf_ed=0.0, ve_ed=0.0):
    return SimpleNamespace(
        f1=f1,
        a_ed=a_ed,
        wf_ed=wf_ed,
        ve_ed=ve_ed,
        ve_cd=0.01,
        r1=1.0,
        requirements=SimpleNamespace(f1=8.0, a_cd=0.1, w_f_cdr1=0.001),
    )


def test_sls2_accepts_frequency_below_8_hz_when_acceleration_passes():
    member = vibration_member(f1=7.0, a_ed=0.05)

    assert struct_optimization_2D.calc_sls2_penalty(member) == 0.0


def test_sls2_penalizes_low_frequency_when_acceleration_also_fails():
    member = vibration_member(f1=7.0, a_ed=0.2)

    assert struct_optimization_2D.calc_sls2_penalty(member) > 0.0
