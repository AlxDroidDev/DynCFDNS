import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import os
from datetime import datetime, timezone
from threading import Lock
import httpx
from cloudflare import Cloudflare

# Import the module under test
import cfupdater


class TestCFUpdater(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset global variables
        cfupdater.__previous_ip = ''
        cfupdater.__last_check = None
        cfupdater.__last_update = None
        cfupdater.__updatable_hosts = {}

    def tearDown(self):
        """Clean up after each test method."""
        # Reset environment variables
        for var in ['CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_API_KEY', 'CLOUDFLARE_API_EMAIL', 'HOST_LIST']:
            if var in os.environ:
                del os.environ[var]

    @patch('httpx.get')
    def test_get_external_ip_success(self, mock_get):
        """Test successful external IP retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {'ip': '203.0.113.1'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = cfupdater.get_external_ip()

        self.assertEqual(result, '203.0.113.1')
        mock_get.assert_called_once_with('https://api.ipify.org?format=json', timeout=httpx.Timeout(15.0))

    @patch('httpx.get')
    @patch('cfupdater.error')
    def test_get_external_ip_failure(self, mock_error, mock_get):
        """Test external IP retrieval failure."""
        mock_get.side_effect = httpx.RequestError("Network error")

        result = cfupdater.get_external_ip()

        self.assertIsNone(result)
        mock_error.assert_called_once()

    @patch('cfupdater.Cloudflare')
    def test_get_record_id_by_name_success(self, mock_cf_class):
        """Test successful DNS record retrieval."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf

        mock_record = Mock()
        mock_record.result_info.count = 1
        mock_record.result = [Mock(id='record123', type='A', proxied=False)]
        mock_cf.dns.records.list.return_value = mock_record

        record_id, record_type, proxied = cfupdater.get_record_id_by_name(
            mock_cf, 'zone123', 'test.example.com'
        )

        self.assertEqual(record_id, 'record123')
        self.assertEqual(record_type, 'A')
        self.assertFalse(proxied)

    @patch('cfupdater.Cloudflare')
    @patch('cfupdater.warn')
    def test_get_record_id_by_name_not_found(self, mock_warn, mock_cf_class):
        """Test DNS record not found scenario."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf

        mock_record = Mock()
        mock_record.result_info.count = 0
        mock_cf.dns.records.list.return_value = mock_record

        record_id, record_type, proxied = cfupdater.get_record_id_by_name(
            mock_cf, 'zone123', 'test.example.com'
        )

        self.assertEqual(record_id, 'Not Found')
        self.assertIsNone(record_type)
        self.assertIsNone(proxied)
        mock_warn.assert_called_once()

    @patch('cfupdater.Cloudflare')
    @patch('cfupdater.info')
    def test_create_new_host_record_success(self, mock_info, mock_cf_class):
        """Test successful creation of new DNS record."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf
        cfupdater.__previous_ip = '203.0.113.1'

        mock_record = Mock(id='record123')
        mock_cf.dns.records.create.return_value = mock_record

        result = cfupdater.create_new_host_record(mock_cf, 'test', 'example.com', 'zone123')

        self.assertEqual(result, 'record123')
        mock_info.assert_called_once()

    @patch('cfupdater.Cloudflare')
    @patch('cfupdater.error')
    def test_create_new_host_record_failure(self, mock_error, mock_cf_class):
        """Test failed creation of new DNS record."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf
        cfupdater.__previous_ip = '203.0.113.1'

        mock_cf.dns.records.create.return_value = None

        result = cfupdater.create_new_host_record(mock_cf, 'test', 'example.com', 'zone123')

        self.assertIsNone(result)
        mock_error.assert_called_once()

    @patch('cfupdater.Cloudflare')
    @patch('cfupdater.info')
    def test_update_cloudflare_dns_record_success(self, mock_info, mock_cf_class):
        """Test successful DNS record update."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf

        mock_record = Mock()
        mock_record.success = True
        mock_cf.dns.records.update.return_value = mock_record

        host_record = {
            'record_id': 'record123',
            'zone_id': 'zone123',
            'content': '203.0.113.1',
            'type': 'A',
            'name': 'test.example.com'
        }

        result = cfupdater.update_cloudflare_dns_record(mock_cf, host_record)

        self.assertTrue(result)
        mock_info.assert_called_once()

    def test_get_domain(self):
        """Test domain extraction from FQDN."""
        result = cfupdater.get_domain('subdomain.example.com')
        self.assertEqual(result, 'example.com')

        result = cfupdater.get_domain('test.co.uk')
        self.assertEqual(result, 'test.co.uk')

    def test_get_tlds(self):
        """Test TLD extraction from host list."""
        host_list = ['test1.example.com', 'test2.example.com', 'api.another.org']
        result = cfupdater.get_tlds(host_list)
        self.assertEqual(result, {'example.com', 'another.org'})

    @patch('cfupdater.assemble_hosts_records')
    @patch('cfupdater.get_external_ip')
    @patch('cfupdater.save_current_ip')
    @patch('cfupdater.update_cloudflare_dns_record')
    @patch('cfupdater.Cloudflare')
    def test_update_dns_records_ip_unchanged(self, mock_cf_class, mock_update, mock_save, mock_get_ip, mock_assemble):
        """Test DNS update when IP hasn't changed."""
        cfupdater.__previous_ip = '203.0.113.1'
        mock_get_ip.return_value = '203.0.113.1'

        result = cfupdater.update_dns_records('token', 'key', 'email', {})

        self.assertTrue(result)
        mock_update.assert_not_called()

    @patch('cfupdater.get_external_ip')
    @patch('cfupdater.error')
    def test_update_dns_records_no_external_ip(self, mock_error, mock_get_ip):
        """Test DNS update when external IP cannot be retrieved."""
        mock_get_ip.return_value = None

        result = cfupdater.update_dns_records('token', 'key', 'email', {})

        self.assertFalse(result)
        mock_error.assert_called_once()

    def test_get_env_var_success(self):
        """Test successful environment variable retrieval."""
        os.environ['TEST_VAR'] = 'test_value'
        result = cfupdater.get_env_var('TEST_VAR')
        self.assertEqual(result, 'test_value')

    def test_get_env_var_with_default(self):
        """Test environment variable retrieval with default value."""
        result = cfupdater.get_env_var('NON_EXISTENT_VAR', 'default_value')
        self.assertEqual(result, 'default_value')

    def test_get_env_var_missing_required(self):
        """Test missing required environment variable."""
        with self.assertRaises(EnvironmentError):
            cfupdater.get_env_var('NON_EXISTENT_VAR')

    @patch('cfupdater.save_attribute_to_config')
    @patch('cfupdater.info')
    def test_save_current_ip_changed(self, mock_info, mock_save_attr):
        """Test saving current IP when it has changed."""
        cfupdater.__previous_ip = '203.0.113.1'
        mock_save_attr.return_value = True

        cfupdater.save_current_ip('203.0.113.2')

        self.assertEqual(cfupdater.__previous_ip, '203.0.113.2')
        mock_save_attr.assert_called_once_with('previous_ip', '203.0.113.2')
        mock_info.assert_called_once()

    @patch('cfupdater.save_attribute_to_config')
    @patch('cfupdater.info')
    def test_save_current_ip_unchanged(self, mock_info, mock_save_attr):
        """Test saving current IP when it hasn't changed."""
        cfupdater.__previous_ip = '203.0.113.1'

        cfupdater.save_current_ip('203.0.113.1')

        mock_save_attr.assert_not_called()
        mock_info.assert_called_once_with("IP has not changed, no update needed.")

    @patch('cfupdater.load_attribute_from_config')
    @patch('cfupdater.save_current_ip')
    def test_load_previous_ip_exists(self, mock_save, mock_load_attr):
        """Test loading previous IP when it exists."""
        mock_load_attr.return_value = '203.0.113.1'

        result = cfupdater.load_previous_ip()

        self.assertEqual(result, '203.0.113.1')
        self.assertEqual(cfupdater.__previous_ip, '203.0.113.1')
        mock_save.assert_not_called()

    @patch('cfupdater.load_attribute_from_config')
    @patch('cfupdater.save_current_ip')
    def test_load_previous_ip_not_exists(self, mock_save, mock_load_attr):
        """Test loading previous IP when it doesn't exist."""
        mock_load_attr.return_value = ''

        result = cfupdater.load_previous_ip()

        mock_save.assert_called_once_with('10.0.0.254')

    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('cfupdater.info')
    def test_check_ip_file_folder_creates_directory(self, mock_info, mock_file, mock_makedirs, mock_exists):
        """Test creating logs directory and IP file."""
        mock_exists.side_effect = [False, False]  # Directory and file don't exist

        cfupdater.check_ip_file_folder()

        mock_makedirs.assert_called_once()
        mock_file.assert_called_once()
        mock_info.assert_called_once()

    def test_thread_safe_getters(self):
        """Test thread-safe getter functions."""
        test_datetime = datetime.now(timezone.utc)
        cfupdater.__last_check = test_datetime
        cfupdater.__last_update = test_datetime
        cfupdater.__previous_ip = '203.0.113.1'
        cfupdater.__updatable_hosts = {'test.com': {}}

        self.assertEqual(cfupdater.get_last_check(), test_datetime)
        self.assertEqual(cfupdater.get_last_update(), test_datetime)
        self.assertEqual(cfupdater.get_previous_ip(), '203.0.113.1')
        self.assertEqual(cfupdater.get_updatable_hosts(), {'test.com': {}})

    @patch('cfupdater.Cloudflare')
    @patch('cfupdater.get_domain')
    @patch('cfupdater.get_tlds')
    @patch('cfupdater.get_record_id_by_name')
    def test_assemble_hosts_records_success(self, mock_get_record, mock_get_tlds, mock_get_domain, mock_cf_class):
        """Test successful assembly of host records."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf

        # Mock zones response
        mock_zone = Mock()
        mock_zone.name = 'example.com'
        mock_zone.id = 'zone123'
        mock_zones = Mock()
        mock_zones.result = [mock_zone]
        mock_cf.zones.list.return_value = mock_zones

        mock_get_tlds.return_value = {'example.com'}
        mock_get_domain.return_value = 'example.com'
        mock_get_record.return_value = ('record123', 'A', False)

        result = cfupdater.assemble_hosts_records('token', 'key', 'email', ['test.example.com'])

        self.assertIn('test.example.com', result)
        self.assertEqual(result['test.example.com']['record_id'], 'record123')

    @patch('cfupdater.Cloudflare')
    @patch('cfupdater.error')
    def test_assemble_hosts_records_no_zones(self, mock_error, mock_cf_class):
        """Test assembly when no zones are found."""
        mock_cf = Mock()
        mock_cf_class.return_value = mock_cf

        mock_zones = Mock()
        mock_zones.result = []
        mock_cf.zones.list.return_value = mock_zones

        result = cfupdater.assemble_hosts_records('token', 'key', 'email', ['test.example.com'])

        self.assertEqual(result, {})
        mock_error.assert_called_once()


if __name__ == '__main__':
    # Configure test runner for coverage
    unittest.main(verbosity=2)