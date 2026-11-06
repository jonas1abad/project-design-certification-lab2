"""Regression for inward wing normals caused by clockwise CPACS DAT export."""
import tempfile
import unittest
from pathlib import Path

from lab2.geometry.airfoil import selig_coordinates, signed_area, validate_selig_airfoil


class AirfoilOrderTests(unittest.TestCase):
    def test_clockwise_profile_is_reversed_without_changing_shape(self):
        original = [(1, 0), (.5, -.03), (0, 0), (.5, .09), (1, 0)]
        corrected = selig_coordinates(original)
        self.assertLess(signed_area(original), 0)
        self.assertGreater(signed_area(corrected), 0)
        self.assertEqual(corrected, original[::-1])
        self.assertEqual(sorted(corrected), sorted(original))
        self.assertEqual(selig_coordinates(corrected), corrected)

    def test_builder_rejects_old_dat_and_accepts_corrected_dat(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'airfoil.dat'
            file.write_text('profile\n1 0\n.5 -.03\n0 0\n.5 .09\n1 0\n')
            with self.assertRaisesRegex(ValueError, 'regenerate DAT'):
                validate_selig_airfoil(file)
            points = selig_coordinates([(1, 0), (.5, -.03), (0, 0), (.5, .09), (1, 0)])
            file.write_text('profile\n' + '\n'.join(f'{x} {z}' for x, z in points))
            validate_selig_airfoil(file)

    def test_degenerate_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'zero signed area'):
            selig_coordinates([(1, 0), (.5, 0), (0, 0), (1, 0)])


if __name__ == '__main__':
    unittest.main()
