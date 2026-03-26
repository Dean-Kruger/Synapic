import os
import queue
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.core import huggingface_utils


class TestHfDownloadProgress(unittest.TestCase):
    def setUp(self):
        huggingface_utils._LOCAL_INFERENCE_COMPAT_CACHE.clear()

    @patch("src.core.huggingface_utils._get_latest_snapshot_path", return_value=None)
    @patch("src.core.huggingface_utils.HfApi")
    def test_mlx_models_are_rejected_for_local_inference(self, mock_hf_api, mock_snapshot_path):
        mock_hf_api.return_value.model_info.return_value = SimpleNamespace(
            library_name="transformers",
            tags=["transformers", "mlx"],
        )

        reason = huggingface_utils.get_local_inference_incompatibility_reason("org/model-MLX", task="image-to-text")

        self.assertIn("MLX", reason)

    @patch("src.core.huggingface_utils._get_latest_snapshot_path", return_value=None)
    @patch("src.core.huggingface_utils.AutoTokenizer")
    @patch("src.core.huggingface_utils.AutoImageProcessor")
    @patch("src.core.huggingface_utils.AutoProcessor")
    @patch("src.core.huggingface_utils.AutoConfig")
    @patch("src.core.huggingface_utils.HfApi")
    def test_models_without_compatible_processor_stack_are_rejected(
        self,
        mock_hf_api,
        mock_auto_config,
        mock_auto_processor,
        mock_auto_image_processor,
        mock_auto_tokenizer,
        mock_snapshot_path,
    ):
        mock_hf_api.return_value.model_info.return_value = SimpleNamespace(
            library_name="transformers",
            tags=["transformers"],
        )
        mock_auto_config.from_pretrained.return_value = object()
        mock_auto_processor.from_pretrained.side_effect = AttributeError("image_token")
        mock_auto_image_processor.from_pretrained.side_effect = ValueError("no image processor")
        mock_auto_tokenizer.from_pretrained.side_effect = KeyError("Florence2Config")

        reason = huggingface_utils.get_local_inference_incompatibility_reason(
            "microsoft/Florence-2-base",
            task="image-to-text",
        )

        self.assertIn("processor/tokenizer", reason)

    @patch("src.core.huggingface_utils.snapshot_download")
    @patch("src.core.huggingface_utils._get_missing_repo_files", return_value=(None, [("weights.bin", 600000)]))
    def test_live_progress_streams_byte_updates(self, mock_missing_files, mock_snapshot_download):
        q = queue.Queue()

        def fake_snapshot_download(*args, **kwargs):
            cm = huggingface_utils.hf_file_download._get_progress_bar_context(
                desc="weights.bin",
                log_level=20,
                total=600000,
                initial=0,
            )
            with cm as progress:
                progress.update(300000)
                progress.update(300000)
            return "C:\\cache\\snapshot"

        mock_snapshot_download.side_effect = fake_snapshot_download

        result = huggingface_utils._download_missing_files_with_progress("org/model", q)

        self.assertEqual(result, "C:\\cache\\snapshot")
        messages = []
        while not q.empty():
            messages.append(q.get_nowait())

        self.assertIn(("total_model_size", 600000), messages)
        self.assertIn(("status_update", "Downloading org/model..."), messages)
        self.assertIn(("model_download_progress", (300000, 600000)), messages)
        self.assertIn(("model_download_progress", (600000, 600000)), messages)

    @patch("src.core.huggingface_utils.is_model_downloaded", return_value=False)
    @patch("src.core.huggingface_utils._download_missing_files_with_progress")
    def test_download_worker_uses_file_progress_helper(self, mock_download_helper, mock_is_downloaded):
        q = queue.Queue()

        huggingface_utils.download_model_worker("org/model", q)

        mock_download_helper.assert_called_once_with("org/model", q, token=None)
        self.assertEqual(q.get_nowait(), ("status_update", "Checking files for org/model..."))
        self.assertEqual(q.get_nowait(), ("download_complete", "org/model"))

    @patch("src.core.huggingface_utils.snapshot_download")
    @patch("src.core.huggingface_utils._get_latest_snapshot_path", return_value="C:\\cache\\snapshot")
    @patch("src.core.huggingface_utils.is_model_downloaded", return_value=True)
    @patch("src.core.huggingface_utils.pipeline")
    def test_load_model_with_progress_uses_cached_snapshot(
        self,
        mock_pipeline,
        mock_is_downloaded,
        mock_snapshot_path,
        mock_snapshot_download,
    ):
        q = queue.Queue()

        huggingface_utils.load_model_with_progress("org/model", "image-to-text", q)

        mock_snapshot_download.assert_not_called()
        mock_pipeline.assert_called_once()
        self.assertEqual(q.get_nowait(), ("status_update", "Initializing model org/model..."))


if __name__ == "__main__":
    unittest.main()
