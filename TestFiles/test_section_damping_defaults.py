import inspect

import pytest

import struct_analysis


@pytest.mark.parametrize(
    "section_class",
    [
        struct_analysis.RectangularWood,
        struct_analysis.RectangularConcrete,
        struct_analysis.PostTensionedConcrete,
        struct_analysis.RibbedConcrete,
        struct_analysis.RibWood,
        struct_analysis.TCC,
    ],
)
def test_all_section_classes_default_to_two_percent_damping(section_class):
    xi_default = inspect.signature(section_class.__init__).parameters["xi"].default

    assert xi_default == pytest.approx(0.02)
