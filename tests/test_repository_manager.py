"""Tests for RepositoryManager clone authentication flow and cleanup."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.repository_manager import RepositoryManager


class TestRepositoryManagerCloneAuth(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_clone_with_token_uses_askpass_and_cleans_up(self):
        mgr = RepositoryManager(cache_dir=self.tmpdir, github_token="ghp_test_token")

        with patch("core.repository_manager._run", return_value=(0, "", "")) as mock_run:
            result = mgr.clone_or_get("https://github.com/acme/repo")

        self.assertTrue(result.is_new_clone)
        self.assertEqual(mock_run.call_count, 1)

        _, kwargs = mock_run.call_args
        env_override = kwargs.get("env_override")
        self.assertIsNotNone(env_override)
        self.assertEqual(env_override.get("GIT_TERMINAL_PROMPT"), "0")
        self.assertIn("GIT_ASKPASS", env_override)
        self.assertFalse(Path(env_override["GIT_ASKPASS"]).exists())

    def test_clone_retry_without_askpass_when_first_attempt_fails(self):
        mgr = RepositoryManager(cache_dir=self.tmpdir, github_token="ghp_test_token")

        with patch(
            "core.repository_manager._run",
            side_effect=[
                (1, "", "auth failed"),
                (0, "", ""),
            ],
        ) as mock_run:
            result = mgr.clone_or_get("https://github.com/acme/repo")

        self.assertTrue(result.is_new_clone)
        self.assertEqual(mock_run.call_count, 2)

        # First call should include askpass; second call should not.
        first_kwargs = mock_run.call_args_list[0].kwargs
        second_kwargs = mock_run.call_args_list[1].kwargs
        self.assertIn("env_override", first_kwargs)
        self.assertNotIn("env_override", second_kwargs)
        self.assertFalse(Path(first_kwargs["env_override"]["GIT_ASKPASS"]).exists())

    def test_clone_failure_still_cleans_up_askpass_script(self):
        mgr = RepositoryManager(cache_dir=self.tmpdir, github_token="ghp_test_token")

        with patch(
            "core.repository_manager._run",
            side_effect=[
                (1, "", "auth failed"),
                (1, "", "still failed"),
            ],
        ) as mock_run:
            with self.assertRaises(RuntimeError):
                mgr.clone_or_get("https://github.com/acme/repo")

        self.assertEqual(mock_run.call_count, 2)
        first_kwargs = mock_run.call_args_list[0].kwargs
        self.assertFalse(Path(first_kwargs["env_override"]["GIT_ASKPASS"]).exists())


if __name__ == "__main__":
    unittest.main()
