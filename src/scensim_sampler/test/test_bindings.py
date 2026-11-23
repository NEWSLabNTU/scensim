"""Issue 131: a scensim FileHeader property names a parameter as param:<name>; a $ there is
refused by name with the form to write (OpenSCENARIO evaluates a FileHeader property before the
parameters exist, so SSv2's preprocessor failed on it)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scensim_sampler.bindings import BindingError, internal, written  # noqa: E402
from scensim_sampler.xosc import Scenario, SpecError  # noqa: E402

XOSC = """<?xml version="1.0"?>
<OpenSCENARIO>
  <FileHeader author="t" date="2026-11-24T00:00:00" description="t" revMajor="1" revMinor="2">
    <Properties>{props}</Properties>
  </FileHeader>
  <ParameterDeclarations>
    <ParameterDeclaration name="light" parameterType="string" value="day"/>
    <ParameterDeclaration name="fog_end" parameterType="double" value="80"/>
    <ParameterDeclaration name="lane" parameterType="string" value="west"/>
    <ParameterDeclaration name="s" parameterType="double" value="10"/>
    <ParameterDeclaration name="exit_lane" parameterType="string" value=""/>
  </ParameterDeclarations>
  <Entities/>
</OpenSCENARIO>
"""


def scenario(d, props):
    p = Path(d) / "s.xosc"
    p.write_text(XOSC.format(props=props))
    return Scenario(p)


class Bindings(unittest.TestCase):
    def test_the_written_and_internal_forms(self):
        self.assertEqual(internal("scensim.pilot_map", "param:pm", "s"), "$pm")
        self.assertEqual(internal("scensim.anchor.x", "param:lane.lanelet_at(param:s)", "s"),
                         "$lane.lanelet_at($s)")
        self.assertEqual(written("time: 0 1000; ${a} $b"), "time: 0 1000; param:a param:b")
        with self.assertRaisesRegex(BindingError, r"s: FileHeader scensim.knob.surface = '\$road'"
                                    r".*issue 131\): write 'param:road'"):
            internal("scensim.knob.surface", "$road", "s")

    def test_each_binding_kind_resolves_from_param(self):
        with tempfile.TemporaryDirectory() as d:
            sc = scenario(d, '<Property name="scensim.knob.illumination" value="param:light"/>'
                             '<Property name="scensim.knob.visibility" '
                             'value="time: 0 1000; 12 param:fog_end"/>'
                             '<Property name="scensim.anchor.exit_lane" '
                             'value="param:lane.lanelet_at(param:s)"/>')
        self.assertEqual(sc.knobs, {"illumination": "light"})
        self.assertIn("visibility", sc.knob_profiles)
        self.assertEqual(sc.anchor_bindings, {"exit_lane": "$lane.lanelet_at($s)"})

    def test_a_dollar_in_any_scensim_property_is_refused_by_name(self):
        for prop, form in (('<Property name="scensim.knob.illumination" value="$light"/>',
                            "param:light"),
                           ('<Property name="scensim.knob.visibility" '
                            'value="time: 0 1000; 12 $fog_end"/>', "time: 0 1000; 12 param:fog_end"),
                           ('<Property name="scensim.anchor.exit_lane" '
                            'value="west.lanelet_at(${s})"/>', "west.lanelet_at(param:s)"),
                           ('<Property name="scensim.pilot_map" value="$light"/>', "param:light")):
            with tempfile.TemporaryDirectory() as d, self.assertRaises(SpecError) as e:
                scenario(d, prop)
            self.assertIn(f"write {form!r}", str(e.exception))

    def test_other_properties_keep_their_values(self):
        with tempfile.TemporaryDirectory() as d:
            sc = scenario(d, '<Property name="note" value="costs $5"/>'
                             '<Property name="scensim.category" value="R1"/>')
        self.assertEqual((sc.properties["note"], sc.category), ("costs $5", "R1"))


if __name__ == "__main__":
    unittest.main()
