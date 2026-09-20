"""
Unit and Integration Tests for Split Inference Components
=========================================================
Verifies model partitioning, socket streaming protocol, edge server,
and unmodified muLinUCB bandit controller functionality.
"""

import sys
import time
import unittest
import torch

from split_inference.controller.muLinUCB import muLinUCB
from split_inference.model.models import PartitionedResNet18, get_resnet18_layer_info
from split_inference.network.server import EdgeInferenceServer
from split_inference.client import SplitInferenceClient


class TestSplitInferenceComponents(unittest.TestCase):
    def setUp(self):
        self.model = PartitionedResNet18(num_classes=10)
        self.model.eval()
        self.dummy_input = torch.randn(1, 3, 224, 224)

    def test_model_partition_numerical_equivalence(self):
        """Validates that for all split points k in {0,1,2,3,4}, forward_split == full forward pass."""
        with torch.no_grad():
            y_full = self.model(self.dummy_input)
            for k in range(5):
                z, y_split = self.model.forward_split(self.dummy_input, k)
                max_diff = (y_full - y_split).abs().max().item()
                self.assertLess(max_diff, 1e-5, f"Split point k={k} numerical mismatch: {max_diff}")

    def test_mulinucb_controller_initialization_and_update(self):
        """Verifies that the unmodified muLinUCB controller initializes and updates properly."""
        layer_info = get_resnet18_layer_info()
        front_delay = [0.0 for _ in range(len(layer_info))]
        controller = muLinUCB(0.25, layer_info, front_delay)

        # Action selection
        action = controller.getEstimationAction(key_frame=True, current_frame=1)
        self.assertIn(action, list(range(len(layer_info))))

        # Update with reward
        controller.updateA_b(action, actual_delay=0.120)
        # Check that matrix A was updated
        self.assertFalse(torch.isnan(torch.tensor(controller.A)).any())

    def test_end_to_end_client_server_inference(self):
        """Verifies full TCP socket communication between EdgeClient and EdgeServer."""
        test_port = 5099
        server = EdgeInferenceServer(host="127.0.0.1", port=test_port)
        server.start(background=True)
        time.sleep(0.5)

        try:
            client = SplitInferenceClient(server_host="127.0.0.1", server_port=test_port)
            client.connect()

            for k in range(5):
                pred, record = client.run_inference(self.dummy_input, forced_k=k, update_controller=False)
                self.assertEqual(record.split_point, k)
                self.assertEqual(pred.shape, (1, 1000))
                self.assertGreater(record.total_latency_ms, 0.0)

            client.close()
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
