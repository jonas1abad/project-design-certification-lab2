"""Native history regression: isolate solver cases and fail on MSVC NaNs."""
from pathlib import Path
import tempfile
import unittest

from lab2.aero.postprocess import read_history


class HistoryTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'case.history'
            file.write_text(text)
            return read_history(file)

    def test_last_iteration_is_separate_from_stability_perturbation(self):
        result = self.parse('Solver Case: 1\nIter Mach AoA Beta CLtot\n'
                            '1 .78 0 0 .4\n2 .78 0 0 .41\n'
                            'Solver Case: 2\nIter Mach AoA Beta CLtot\n'
                            '1 .78 1 0 .51\n')
        self.assertEqual(result[1]['CLtot'], .41)
        self.assertEqual(result[2]['AoA'], 1)

    def test_msvc_nan_is_rejected_even_if_later_iteration_is_finite(self):
        with self.assertRaisesRegex(ValueError, 'Nonfinite solver output'):
            self.parse('Solver Case: 1\nIter Mach AoA Beta CLtot\n'
                       '1 .78 0 0 -nan(ind)\n2 .78 0 0 .41\n')


if __name__ == '__main__':
    unittest.main()
