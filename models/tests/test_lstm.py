from __future__ import annotations

import unittest

import numpy as np

from src.models.lstm import create_sequences


class LSTMTests(unittest.TestCase):
    def test_create_sequences_uses_last_label_in_window(self) -> None:
        features = np.array([[1.0], [2.0], [3.0], [4.0]], dtype=np.float32)
        labels = np.array([0, 1, 2, 1], dtype=np.int64)

        x_sequences, y_sequences = create_sequences(features, labels, sequence_length=3)

        self.assertEqual(x_sequences.shape, (2, 3, 1))
        self.assertEqual(y_sequences.tolist(), [2, 1])
        self.assertEqual(x_sequences[0, :, 0].tolist(), [1.0, 2.0, 3.0])
        self.assertEqual(x_sequences[1, :, 0].tolist(), [2.0, 3.0, 4.0])


if __name__ == "__main__":
    unittest.main()
