import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from siemens_star import create_siemens_star, save_svg


SVG = "{http://www.w3.org/2000/svg}"


class SiemensStarTests(unittest.TestCase):
    def test_a4_two_degree_star(self):
        root = create_siemens_star(angle_deg=2, paper="A4")

        self.assertEqual(root.attrib["width"], "210mm")
        self.assertEqual(root.attrib["height"], "297mm")
        self.assertEqual(len(root.findall("./g/path")), 90)

    def test_a3_five_degree_landscape_star(self):
        root = create_siemens_star(
            angle_deg=5,
            paper="A3",
            orientation="landscape",
        )

        self.assertEqual(root.attrib["width"], "420mm")
        self.assertEqual(root.attrib["height"], "297mm")
        self.assertEqual(len(root.findall("./g/path")), 36)

    def test_saved_svg_is_valid_xml_with_physical_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "star.svg"
            save_svg(create_siemens_star(5), output)
            parsed = ET.parse(output).getroot()

        self.assertEqual(parsed.tag, f"{SVG}svg")
        self.assertEqual(parsed.attrib["width"], "210mm")
        self.assertEqual(len(parsed.findall(f"./{SVG}g/{SVG}path")), 36)

    def test_rejects_angle_that_does_not_close_circle(self):
        with self.assertRaisesRegex(ValueError, "整除 360"):
            create_siemens_star(angle_deg=7)

    def test_rejects_radius_outside_printable_area(self):
        with self.assertRaisesRegex(ValueError, "半徑過大"):
            create_siemens_star(angle_deg=5, paper="A4", radius_mm=100)


if __name__ == "__main__":
    unittest.main()
