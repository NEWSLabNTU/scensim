"""The compile step (092 K2.2): a scenario and N records as the batch's entity table, per-slot
parameters, initial poses and speeds; refused by name outside what it compiles, and when the
environment does not meet the verdict's conditions."""
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "scensim_sampler"))

try:
    import torch
except ImportError:
    torch = None

CASES = HERE.parents[1] / "scensim_sampler" / "examples" / "cases"


class StraightWorld:
    """Lanes as parallel lines along x: lane id k at y = 3.5 * (k - 34513)."""

    def lane_pose(self, lanes, s, offset):
        y = torch.tensor([3.5 * (int(l) - 34513) for l in lanes], dtype=torch.float64)
        return s, y + offset, torch.zeros_like(s)


def rec(**values):
    return {"values": values, "seeds": {"scenario": 7}}


@unittest.skipIf(torch is None, "no torch")
class Compile(unittest.TestCase):
    def setUp(self):
        from scensim_batch import compile as C
        self.C = C

    def test_cs2_per_slot_values_poses_and_roles(self):
        recs = [rec(ego_speed=20.0, decel=6.0), rec(ego_speed=25.0, decel=7.5), rec()]
        c = self.C.compile_scenario(CASES / "cs2_lead_brakes_wet_night.xosc", recs,
                                    StraightWorld(), provides=("world knob illumination=night",))
        self.assertEqual(c.n, 3)
        self.assertEqual([(e.name, e.role) for e in c.entities], [("ego", "ego"),
                                                                    ("lead", "default")])
        ego, lead = c.index("ego"), c.index("lead")
        self.assertEqual(c.speed[:, ego].tolist(), [20.0, 25.0, 22.0])   # 22: the default
        self.assertEqual(c.params["decel"].tolist(), [6.0, 7.5, 6.5])
        self.assertEqual(c.x[:, lead].tolist(), [36.0] * 3)
        self.assertEqual(c.entities[lead].length, 4.7)
        self.assertTrue(bool(c.placed.all()))
        self.assertEqual(c.params["world.surface"], ["wet"] * 3)

    def test_an_unmet_condition_is_refused_with_what_is_provided(self):
        with self.assertRaisesRegex(self.C.CompileError,
                                    r"compiles only if: world knob illumination=night"):
            self.C.compile_scenario(CASES / "cs2_lead_brakes_wet_night.xosc", [rec()],
                                    StraightWorld())

    def test_a_refused_scenario_and_an_uncompiled_construct_are_named(self):
        with self.assertRaisesRegex(self.C.CompileError, "refused: TimeToCollisionCondition"):
            self.C.compile_scenario(CASES / "cs1_walker_dartout_ttc.xosc", [rec()],
                                    StraightWorld())
        # the walker is a model entity (092 K10): only its model moves it, so the description
        # example's storyboard SpeedAction on it is refused, by name (the batch example,
        # cs1_walker_gap_acceptance.xosc, leaves the walker to its model: test_models.py)
        with self.assertRaisesRegex(self.C.CompileError, "SpeedAction on 'walker', a model "
                                                         "entity"):
            self.C.compile_scenario(CASES / "cs1_walker_dartout.xosc", [rec()], StraightWorld())

    def test_relative_positions_follow_their_reference_per_slot(self):
        xosc = """<?xml version="1.0"?><OpenSCENARIO>
  <ParameterDeclarations><ParameterDeclaration name="gap" parameterType="double" value="10"/>
  </ParameterDeclarations>
  <Entities>
    <ScenarioObject name="ego"><Vehicle name="c"><BoundingBox><Center x="0" y="0" z="0"/>
      <Dimensions length="4" width="2" height="1.5"/></BoundingBox></Vehicle>
      <ObjectController><Controller name="e"><Properties><Property name="isEgo" value="true"/>
      </Properties></Controller></ObjectController></ScenarioObject>
    <ScenarioObject name="cone"><MiscObject name="cone"><BoundingBox><Center x="0" y="0" z="0"/>
      <Dimensions length="0.4" width="0.4" height="0.7"/></BoundingBox></MiscObject></ScenarioObject>
  </Entities>
  <Storyboard><Init><Actions>
    <Private entityRef="ego"><PrivateAction><TeleportAction><Position>
      <WorldPosition x="5" y="1" h="1.5707963267948966"/></Position></TeleportAction></PrivateAction></Private>
    <Private entityRef="cone"><PrivateAction><TeleportAction><Position>
      <RelativeObjectPosition entityRef="ego" dx="$gap" dy="0"/></Position></TeleportAction></PrivateAction></Private>
  </Actions></Init><StopTrigger/></Storyboard></OpenSCENARIO>"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.xosc"
            p.write_text(xosc)
            c = self.C.compile_scenario(p, [rec(gap=10.0), rec(gap=20.0)], StraightWorld())
        cone = c.index("cone")
        self.assertEqual(c.entities[cone].role, "prop")
        for i, g in enumerate((10.0, 20.0)):   # ahead of the ego, which faces +y
            self.assertAlmostEqual(c.x[i, cone].item(), 5.0, places=9)
            self.assertAlmostEqual(c.y[i, cone].item(), 1.0 + g, places=9)
        self.assertAlmostEqual(c.yaw[0, cone].item(), math.pi / 2, places=12)

    CATALOG_XOSC = """<?xml version="1.0"?><OpenSCENARIO>
  <CatalogLocations><VehicleCatalog><Directory path="DIR"/></VehicleCatalog></CatalogLocations>
  <Entities>
    <ScenarioObject name="ego"><CatalogReference catalogName="vehicles" entryName="ENTRY"/>
      <ObjectController><Controller name="e"><Properties><Property name="isEgo" value="true"/>
      </Properties></Controller></ObjectController></ScenarioObject>
    <ScenarioObject name="npc"><CatalogReference catalogName="vehicles" entryName="ENTRY"/>
    </ScenarioObject>
  </Entities>
  <Storyboard><Init><Actions>
    <Private entityRef="ego"><PrivateAction><TeleportAction><Position>
      <WorldPosition x="0" y="0" h="0"/></Position></TeleportAction></PrivateAction></Private>
    <Private entityRef="npc"><PrivateAction><TeleportAction><Position>
      <WorldPosition x="20" y="0" h="0"/></Position></TeleportAction></PrivateAction></Private>
  </Actions></Init><StopTrigger/></Storyboard></OpenSCENARIO>"""
    CATALOG = """<?xml version="1.0"?><OpenSCENARIO><Catalog name="vehicles">
  <Vehicle name="car" vehicleCategory="car"><BoundingBox><Center x="1.4" y="0" z="0.7"/>
    <Dimensions length="4.8" width="2.1" height="1.5"/></BoundingBox></Vehicle>
  <Vehicle name="param" vehicleCategory="car"><BoundingBox><Center x="1.4" y="0" z="0.7"/>
    <Dimensions length="$len" width="2.1" height="1.5"/></BoundingBox></Vehicle>
</Catalog></OpenSCENARIO>"""

    def _catalog_case(self, d, directory, entry="car"):
        (d / "cat").mkdir(exist_ok=True)
        (d / "cat" / "vehicles.xosc").write_text(self.CATALOG)
        p = d / "s.xosc"
        p.write_text(self.CATALOG_XOSC.replace("DIR", directory).replace("ENTRY", entry))
        return p

    def test_catalog_entities_from_the_scenarios_locations(self):
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            c = self.C.compile_scenario(self._catalog_case(d, "cat"), [rec()], StraightWorld())
            npc = c.entities[c.index("npc")]
            self.assertEqual((npc.role, npc.length, npc.width, npc.cx), ("default", 4.8, 2.1, 1.4))
            self.assertEqual(c.entities[c.index("ego")].role, "ego")
            p = self._catalog_case(d, "$(env TEST_SCENSIM_VEHICLES)")
            with mock.patch.dict(os.environ, {"TEST_SCENSIM_VEHICLES": str(d / "cat")}):
                c = self.C.compile_scenario(p, [rec()], StraightWorld())
            self.assertEqual(c.entities[c.index("npc")].length, 4.8)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TEST_SCENSIM_VEHICLES", None)
                with self.assertRaisesRegex(self.C.CompileError,
                                            "TEST_SCENSIM_VEHICLES not in the environment"):
                    self.C.compile_scenario(p, [rec()], StraightWorld())
                # given by name, the catalog needs no environment
                c = self.C.compile_scenario(p, [rec()], StraightWorld(),
                                            catalogs={"vehicles": d / "cat" / "vehicles.xosc"})
            self.assertEqual(c.entities[c.index("npc")].width, 2.1)

    def test_an_empty_controller_is_the_default_vehicle(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p = self._catalog_case(d, "cat")
            empty = p.read_text().replace(
                '<CatalogReference catalogName="vehicles" entryName="car"/>\n    </ScenarioObject>',
                '<CatalogReference catalogName="vehicles" entryName="car"/>\n    <ObjectController>'
                '<Controller name=""><Properties/></Controller></ObjectController></ScenarioObject>')
            self.assertNotEqual(empty, p.read_text())
            p.write_text(empty)
            c = self.C.compile_scenario(p, [rec()], StraightWorld())
            self.assertEqual(c.entities[c.index("npc")].role, "default")
            p.write_text(empty.replace("<Properties/>",
                                       '<Properties><Property name="maxSpeed" value="5"/>'
                                       '</Properties>'))
            with self.assertRaisesRegex(self.C.CompileError, "with a controller"):
                self.C.compile_scenario(p, [rec()], StraightWorld())

    def test_catalog_entry_missing_or_parameterised_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            with self.assertRaisesRegex(self.C.CompileError, "has no 'nope'"):
                self.C.compile_scenario(self._catalog_case(d, "cat", "nope"), [rec()],
                                        StraightWorld())
            with self.assertRaisesRegex(self.C.CompileError, "Dimensions@length is a parameter"):
                self.C.compile_scenario(self._catalog_case(d, "cat", "param"), [rec()],
                                        StraightWorld())

    def test_no_records_is_refused(self):
        with self.assertRaisesRegex(self.C.CompileError, "no records"):
            self.C.compile_scenario(CASES / "cs4_lidar_dropout_cutin.xosc", [], StraightWorld())


if __name__ == "__main__":
    unittest.main()
