"""Reject the shared-four-face edge found at the coarse WBH tail junction."""
from pathlib import Path
import tempfile
import unittest

from lab2.aero.mesh import check_panel_mesh


class PanelMeshTests(unittest.TestCase):
    def check(self, faces):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'mesh.vspgeom'
            file.write_text('4\n0 0 0\n1 0 0\n0 1 0\n0 0 1\n' + str(len(faces)) + '\n' + '\n'.join(faces))
            return check_panel_mesh(file)

    def test_closed_tetrahedron(self):
        result = self.check(['3 1 2 3', '3 1 4 2', '3 1 3 4', '3 2 4 3'])
        self.assertEqual(result['edges'], 6)

    def test_shared_four_face_edge_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not a closed manifold'):
            self.check(['3 1 2 3', '3 1 4 2', '3 1 3 4', '3 2 4 3', '3 1 2 3', '3 1 4 2'])


if __name__ == '__main__':
    unittest.main()
