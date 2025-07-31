import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import json
import tempfile
from datetime import datetime, timezone, timedelta

# Import the module under test
import healthcheck


class TestHealthCheck(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Store original values
        self.original_health_file_path = healthcheck.HEALTH_FILE_FULL_PATH

        # Set up test file path
        test_temp_dir = tempfile.gettempdir()
        healthcheck.HEALTH_FILE_FULL_PATH = os.path.join(test_temp_dir, "test_dyncfdns_health.json")

    def tearDown(self):
        """Clean up after each test method."""
        # Restore original values
        healthcheck.HEALTH_FILE_FULL_PATH = self.original_health_file_path

        # Clean up test files
        try:
            if os.path.exists(healthcheck.HEALTH_FILE_FULL_PATH):
                os.remove(healthcheck.HEALTH_FILE_FULL_PATH)
        except OSError:
            pass

    def test_constants(self):
        """Test that constants are properly defined."""
        self.assertEqual(healthcheck.HEALTH_FILE, "dyncfdns_health.json")
        self.assertIn(healthcheck.HEALTH_FILE, healthcheck.HEALTH_FILE_FULL_PATH)

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_write_health_status_success(self, mock_json_dump, mock_file):
        """Test successful health status write."""
        test_time = datetime.now(timezone.utc)

        result = healthcheck.write_health_status(test_time)

        self.assertTrue(result)
        mock_file.assert_called_once_with(healthcheck.HEALTH_FILE_FULL_PATH, 'w')
        mock_json_dump.assert_called_once()

        # Verify the data structure passed to json.dump
        call_args = mock_json_dump.call_args[0]
        health_data = call_args[0]
        self.assertEqual(health_data['last_check'], test_time.isoformat())
        self.assertEqual(health_data['status'], 'running')

    def test_write_health_status_default_time(self):
        """Test write_health_status with default timestamp."""
        with patch('builtins.open', mock_open()):
            with patch('json.dump'):
                result = healthcheck.write_health_status()
                self.assertTrue(result)

    @patch('builtins.open')
    @patch('healthcheck.error')
    def test_write_health_status_file_error(self, mock_error, mock_open):
        """Test write_health_status with file I/O error."""
        mock_open.side_effect = IOError("Permission denied")

        result = healthcheck.write_health_status()

        self.assertFalse(result)
        mock_error.assert_called_once()

    @patch('json.dump')
    @patch('builtins.open')
    @patch('healthcheck.error')
    def test_write_health_status_json_error(self, mock_error, mock_file, mock_json_dump):
        """Test write_health_status with JSON serialization error."""
        mock_json_dump.side_effect = json.JSONEncodeError("Invalid JSON", "", 0)

        result = healthcheck.write_health_status()

        self.assertFalse(result)
        mock_error.assert_called_once()

    @patch('os.path.exists')
    def test_check_health_file_not_exists(self, mock_exists):
        """Test check_health when health file doesn't exist."""
        mock_exists.return_value = False

        result = healthcheck.check_health()

        self.assertFalse(result)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_check_health_success_recent(self, mock_json_load, mock_file, mock_exists):
        """Test check_health with recent timestamp (healthy)."""
        mock_exists.return_value = True

        # Create a recent timestamp
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        mock_json_load.return_value = {
            'last_check': recent_time.isoformat(),
            'status': 'running'
        }

        result = healthcheck.check_health()

        self.assertTrue(result)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('healthcheck.UPDATE_INTERVAL', 120)
    def test_check_health_success_within_grace_period(self, mock_json_load, mock_file, mock_exists):
        """Test check_health with timestamp within grace period."""
        mock_exists.return_value = True

        # Create a timestamp just within grace period (UPDATE_INTERVAL + 10 seconds)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=130)
        mock_json_load.return_value = {
            'last_check': old_time.isoformat(),
            'status': 'running'
        }

        result = healthcheck.check_health()

        self.assertTrue(result)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('healthcheck.UPDATE_INTERVAL', 120)
    def test_check_health_failure_too_old(self, mock_json_load, mock_file, mock_exists):
        """Test check_health with old timestamp (unhealthy)."""
        mock_exists.return_value = True

        # Create a timestamp beyond grace period (UPDATE_INTERVAL + 20 seconds)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=140)
        mock_json_load.return_value = {
            'last_check': old_time.isoformat(),
            'status': 'running'
        }

        result = healthcheck.check_health()

        self.assertFalse(result)

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('healthcheck.error')
    def test_check_health_file_read_error(self, mock_error, mock_open, mock_exists):
        """Test check_health with file read error."""
        mock_exists.return_value = True
        mock_open.side_effect = IOError("Permission denied")

        result = healthcheck.check_health()

        self.assertFalse(result)
        mock_error.assert_called_once()

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('healthcheck.error')
    def test_check_health_json_decode_error(self, mock_error, mock_json_load, mock_file, mock_exists):
        """Test check_health with JSON decode error."""
        mock_exists.return_value = True
        mock_json_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        result = healthcheck.check_health()

        self.assertFalse(result)
        mock_error.assert_called_once()

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    @patch('healthcheck.error')
    def test_check_health_invalid_datetime(self, mock_error, mock_json_load, mock_file, mock_exists):
        """Test check_health with invalid datetime format."""
        mock_exists.return_value = True
        mock_json_load.return_value = {
            'last_check': 'invalid-datetime-format',
            'status': 'running'
        }

        result = healthcheck.check_health()

        self.assertFalse(result)
        mock_error.assert_called_once()

    @patch('os.getenv')
    def test_is_running_in_docker_env_var_docker_container(self, mock_getenv):
        """Test Docker detection via DOCKER_CONTAINER environment variable."""
        mock_getenv.side_effect = lambda key: 'true' if key == 'DOCKER_CONTAINER' else None

        result = healthcheck.is_running_in_docker()

        self.assertTrue(result)

    @patch('os.getenv')
    def test_is_running_in_docker_env_var_container(self, mock_getenv):
        """Test Docker detection via CONTAINER environment variable."""
        mock_getenv.side_effect = lambda key: 'true' if key == 'CONTAINER' else None

        result = healthcheck.is_running_in_docker()

        self.assertTrue(result)

    @patch('os.getenv')
    @patch('os.path.exists')
    def test_is_running_in_docker_dockerenv_file(self, mock_exists, mock_getenv):
        """Test Docker detection via .dockerenv file."""
        mock_getenv.return_value = None
        mock_exists.return_value = True

        result = healthcheck.is_running_in_docker()

        self.assertTrue(result)
        mock_exists.assert_called_with('/.dockerenv')

    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_is_running_in_docker_cgroup_docker(self, mock_file, mock_exists, mock_getenv):
        """Test Docker detection via cgroup with 'docker' in content."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_file.return_value.read.return_value = "12:memory:/docker/container123"

        result = healthcheck.is_running_in_docker()

        self.assertTrue(result)

    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_is_running_in_docker_cgroup_containerd(self, mock_file, mock_exists, mock_getenv):
        """Test Docker detection via cgroup with 'containerd' in content."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_file.return_value.read.return_value = "12:memory:/containerd/container123"

        result = healthcheck.is_running_in_docker()

        self.assertTrue(result)

    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_is_running_in_docker_cgroup_no_docker(self, mock_file, mock_exists, mock_getenv):
        """Test Docker detection via cgroup without Docker indicators."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_file.return_value.read.return_value = "12:memory:/system.slice/service"

        result = healthcheck.is_running_in_docker()

        self.assertFalse(result)

    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('builtins.open')
    def test_is_running_in_docker_cgroup_file_not_found(self, mock_open, mock_exists, mock_getenv):
        """Test Docker detection when cgroup file doesn't exist."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_open.side_effect = FileNotFoundError()

        result = healthcheck.is_running_in_docker()

        self.assertFalse(result)

    @patch('os.getenv')
    @patch('os.path.exists')
    @patch('builtins.open')
    def test_is_running_in_docker_cgroup_permission_error(self, mock_open, mock_exists, mock_getenv):
        """Test Docker detection when cgroup file has permission error."""
        mock_getenv.return_value = None
        mock_exists.return_value = False
        mock_open.side_effect = PermissionError()

        result = healthcheck.is_running_in_docker()

        self.assertFalse(result)

    @patch('healthcheck.check_health')
    @patch('sys.exit')
    def test_main_healthy(self, mock_exit, mock_check_health):
        """Test main function when service is healthy."""
        mock_check_health.return_value = True

        healthcheck.main()

        mock_exit.assert_called_once_with(0)

    @patch('healthcheck.check_health')
    @patch('sys.exit')
    def test_main_unhealthy(self, mock_exit, mock_check_health):
        """Test main function when service is unhealthy."""
        mock_check_health.return_value = False

        healthcheck.main()

        mock_exit.assert_called_once_with(1)

    @patch('healthcheck.main')
    def test_main_execution(self, mock_main):
        """Test that main is called when script is executed directly."""
        # This would be tested by running the module directly
        # For unit testing, we just verify the structure
        self.assertTrue(hasattr(healthcheck, 'main'))
        self.assertTrue(callable(healthcheck.main))


if __name__ == '__main__':
    # Run tests with coverage
    unittest.main(verbosity=2)