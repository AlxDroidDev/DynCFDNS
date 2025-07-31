import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import json
from base64 import b64decode

# Import the module under test
import globals


class TestGlobals(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Clear environment variables
        self.env_vars_to_clear = ['UPDATE_INTERVAL', 'API_PORT', 'API_TOKEN']
        self.original_env = {}
        for var in self.env_vars_to_clear:
            if var in os.environ:
                self.original_env[var] = os.environ[var]
                del os.environ[var]

    def tearDown(self):
        """Clean up after each test method."""
        # Restore original environment variables
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
            if var in self.original_env:
                os.environ[var] = self.original_env[var]

    def test_get_update_interval_default(self):
        """Test get_update_interval returns default value when env var not set."""
        result = globals.get_update_interval()
        self.assertEqual(result, 120)

    def test_get_update_interval_from_env(self):
        """Test get_update_interval returns value from environment variable."""
        os.environ['UPDATE_INTERVAL'] = '300'
        result = globals.get_update_interval()
        self.assertEqual(result, 300)

    def test_get_update_interval_minimum_value(self):
        """Test get_update_interval enforces minimum value of 1."""
        os.environ['UPDATE_INTERVAL'] = '0'
        result = globals.get_update_interval()
        self.assertEqual(result, 1)

        os.environ['UPDATE_INTERVAL'] = '-10'
        result = globals.get_update_interval()
        self.assertEqual(result, 1)

    @patch('globals.warn')
    def test_get_update_interval_invalid_value(self, mock_warn):
        """Test get_update_interval handles invalid values gracefully."""
        os.environ['UPDATE_INTERVAL'] = 'invalid'
        result = globals.get_update_interval()

        self.assertEqual(result, 120)
        mock_warn.assert_called_once_with(
            "Expected UPDATE_INTERVAL to be a valid integer. Using default value of 2 minutes.")

    def test_get_api_port_default(self):
        """Test get_api_port returns default value when env var not set."""
        result = globals.get_api_port()
        self.assertEqual(result, 5000)

    def test_get_api_port_from_env(self):
        """Test get_api_port returns value from environment variable."""
        os.environ['API_PORT'] = '8080'
        result = globals.get_api_port()
        self.assertEqual(result, 8080)

    def test_get_api_port_minimum_value(self):
        """Test get_api_port enforces minimum value of 0."""
        os.environ['API_PORT'] = '-1'
        result = globals.get_api_port()
        self.assertEqual(result, 0)

    @patch('globals.warn')
    def test_get_api_port_invalid_value(self, mock_warn):
        """Test get_api_port handles invalid values gracefully."""
        os.environ['API_PORT'] = 'invalid'
        result = globals.get_api_port()

        self.assertEqual(result, 0)
        mock_warn.assert_called_once_with("API_PORT is set but is not a valid integer. Disabling API.")

    @patch('globals.API_PORT', 0)
    def test_get_api_token_api_disabled(self):
        """Test get_api_token returns empty string when API is disabled."""
        result = globals.get_api_token()
        self.assertEqual(result, '')

    @patch('globals.API_PORT', 5000)
    @patch('globals.save_attribute_to_config')
    def test_get_api_token_from_env(self, mock_save):
        """Test get_api_token returns value from environment variable."""
        os.environ['API_TOKEN'] = 'test_token_from_env'
        mock_save.return_value = True

        result = globals.get_api_token()

        self.assertEqual(result, 'test_token_from_env')
        mock_save.assert_called_once_with('api_token', 'test_token_from_env')

    @patch('globals.API_PORT', 5000)
    @patch('globals.load_attribute_from_config')
    def test_get_api_token_from_config(self, mock_load):
        """Test get_api_token returns value from config file."""
        mock_load.return_value = 'test_token_from_config'

        result = globals.get_api_token()

        self.assertEqual(result, 'test_token_from_config')

    @patch('globals.API_PORT', 5000)
    @patch('globals.load_attribute_from_config')
    @patch('globals.save_attribute_to_config')
    @patch('globals.info')
    def test_get_api_token_generates_new(self, mock_info, mock_save, mock_load):
        """Test get_api_token generates new token when none exists."""
        mock_load.return_value = ''
        mock_save.return_value = True

        result = globals.get_api_token()

        # Verify token is base64 encoded and has correct length
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

        # Verify it's valid base64
        try:
            decoded = b64decode(result)
            self.assertEqual(len(decoded), 32)  # 32 bytes
        except Exception:
            self.fail("Generated token is not valid base64")

        mock_save.assert_called_once_with('api_token', result)
        mock_info.assert_called_once()

    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_attribute_to_config_new_file(self, mock_file, mock_exists, mock_makedirs):
        """Test save_attribute_to_config creates new config file."""
        mock_exists.return_value = False

        result = globals.save_attribute_to_config('test_key', 'test_value')

        self.assertTrue(result)
        mock_makedirs.assert_called_once_with(os.path.dirname(globals.__CONFIG_PATH), exist_ok=True)

        # Verify file was written with correct JSON
        handle = mock_file.return_value
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        config = json.loads(written_data)
        self.assertEqual(config['test_key'], 'test_value')

    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_attribute_to_config_existing_file(self, mock_file, mock_exists, mock_makedirs):
        """Test save_attribute_to_config updates existing config file."""
        mock_exists.return_value = True
        existing_config = {'existing_key': 'existing_value'}
        mock_file.return_value.read.return_value = json.dumps(existing_config)

        result = globals.save_attribute_to_config('new_key', 'new_value')

        self.assertTrue(result)

        # Verify existing data is preserved and new data is added
        handle = mock_file.return_value
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        config = json.loads(written_data)
        self.assertEqual(config['existing_key'], 'existing_value')
        self.assertEqual(config['new_key'], 'new_value')

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_attribute_to_config_invalid_json(self, mock_file, mock_exists):
        """Test save_attribute_to_config handles invalid JSON gracefully."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = 'invalid json'

        result = globals.save_attribute_to_config('test_key', 'test_value')

        self.assertTrue(result)

        # Should create new config when existing file has invalid JSON
        handle = mock_file.return_value
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        config = json.loads(written_data)
        self.assertEqual(config['test_key'], 'test_value')

    @patch('os.makedirs')
    @patch('globals.warn')
    def test_save_attribute_to_config_io_error(self, mock_warn, mock_makedirs):
        """Test save_attribute_to_config handles IO errors gracefully."""
        mock_makedirs.side_effect = IOError("Permission denied")

        result = globals.save_attribute_to_config('test_key', 'test_value')

        self.assertFalse(result)
        mock_warn.assert_called_once()

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_attribute_from_config_success(self, mock_file, mock_exists):
        """Test load_attribute_from_config returns value from config file."""
        mock_exists.return_value = True
        config_data = {'test_key': 'test_value'}
        mock_file.return_value.read.return_value = json.dumps(config_data)

        result = globals.load_attribute_from_config('test_key')

        self.assertEqual(result, 'test_value')

    @patch('os.path.exists')
    def test_load_attribute_from_config_file_not_exists(self, mock_exists):
        """Test load_attribute_from_config returns default when file doesn't exist."""
        mock_exists.return_value = False

        result = globals.load_attribute_from_config('test_key', 'default_value')

        self.assertEqual(result, 'default_value')

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_attribute_from_config_key_not_found(self, mock_file, mock_exists):
        """Test load_attribute_from_config returns default when key not found."""
        mock_exists.return_value = True
        config_data = {'other_key': 'other_value'}
        mock_file.return_value.read.return_value = json.dumps(config_data)

        result = globals.load_attribute_from_config('missing_key', 'default_value')

        self.assertEqual(result, 'default_value')

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('globals.warn')
    def test_load_attribute_from_config_invalid_json(self, mock_warn, mock_file, mock_exists):
        """Test load_attribute_from_config handles invalid JSON gracefully."""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = 'invalid json'

        result = globals.load_attribute_from_config('test_key', 'default_value')

        self.assertEqual(result, 'default_value')
        mock_warn.assert_called_once()

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('globals.warn')
    def test_load_attribute_from_config_io_error(self, mock_warn, mock_open, mock_exists):
        """Test load_attribute_from_config handles IO errors gracefully."""
        mock_exists.return_value = True
        mock_open.side_effect = IOError("Permission denied")

        result = globals.load_attribute_from_config('test_key', 'default_value')

        self.assertEqual(result, 'default_value')
        mock_warn.assert_called_once()

    def test_constants_defined(self):
        """Test that all expected constants are defined."""
        self.assertEqual(globals.NOT_FOUND, 'Not Found')
        self.assertEqual(globals.KEY_PREVIOUS_IP, 'previous_ip')
        self.assertIsInstance(globals.API_PORT, int)
        self.assertIsInstance(globals.UPDATE_INTERVAL, int)
        self.assertIsInstance(globals.API_TOKEN, str)

    def test_config_path_constant(self):
        """Test that config path constant is properly defined."""
        self.assertEqual(globals.__CONFIG_PATH, './config/.config.json')


if __name__ == '__main__':
    # Run tests with coverage
    unittest.main(verbosity=2)