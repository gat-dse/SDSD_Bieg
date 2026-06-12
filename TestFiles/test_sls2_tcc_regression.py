from types import SimpleNamespace

import struct_optimization


def make_member(*, f1, a_ed):
    requirements = SimpleNamespace(
        f1=8.0,
        a_cd=0.05,
        w_f_cdr1=1.0,
    )
    return SimpleNamespace(
        requirements=requirements,
        f1=f1,
        a_ed=a_ed,
        wf_ed=0.0,
        r1=1.0,
        ve_ed=0.0,
        ve_cd=1.0,
    )


def test_frequency_or_acceleration_can_satisfy_resonance_check():
    member = make_member(f1=7.5, a_ed=0.04)

    assert struct_optimization.calc_sls2_penalty(member) == 0.0


def test_resonance_penalty_applies_when_frequency_and_acceleration_fail():
    member = make_member(f1=7.5, a_ed=0.06)

    assert struct_optimization.calc_sls2_penalty(member) > 0.0
