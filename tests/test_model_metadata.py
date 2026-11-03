"""Configuration provenance checks; credentials are deliberately fake."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from collective101.console import MissionConsole

ROOT=Path(__file__).resolve().parents[1]

class ModelMetadataTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work'/'model-metadata-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.console=MissionConsole(Path(self.temp.name)/'state.db')
        self.env=patch.dict('os.environ',{'MODEL_API_KEY':'','META_MODEL':'','MODEL_MAX_OUTPUT_TOKENS':'','MODEL_REQUEST_TIMEOUT_SECONDS':''})
        self.env.start()
    def tearDown(self):
        self.env.stop();self.console.close();self.temp.cleanup()
    def test_environment_source_visible_without_disclosing_key(self):
        from collective101.provider import MetaProvider
        self.assertEqual(MetaProvider(api_key='test-only').model,'muse-spark-1.3')
        with patch.dict('os.environ',{'MODEL_API_KEY':'environment-secret-placeholder','META_MODEL':'muse-spark-1.3'}):
            health=self.console.health();config=health['model_configuration']
            self.assertTrue(config['configured']);self.assertEqual(config['credential_source'],'environment')
            self.assertEqual(config['settings_source'],'environment_defaults');self.assertEqual(config['model'],'muse-spark-1.3')
            self.assertEqual(config['endpoint_host'],'api.meta.ai')
            self.assertNotIn('environment-secret-placeholder',json.dumps(health))
    def test_saved_precedence_disabled_and_missing_states(self):
        manager=self.console.connectors
        self.assertEqual(manager.model_configuration()['credential_source'],'none')
        manager.save({'kind':'meta','name':'Test model','secret':'saved-placeholder-secret','model':'test-model'})
        with patch.dict('os.environ',{'MODEL_API_KEY':'environment-placeholder-secret'}):
            config=manager.model_configuration()
            self.assertEqual(config['credential_source'],'saved_connector');self.assertEqual(config['model'],'test-model')
            manager.disable('model');self.assertFalse(manager.model_configuration()['configured'])
            self.assertFalse(manager.model_configuration()['enabled'])
            self.assertNotIn('placeholder-secret',json.dumps(manager.model_configuration()))
    def test_environment_key_with_saved_endpoint_and_request_options(self):
        manager=self.console.connectors
        manager.save({'kind':'meta','name':'Model settings','model':'test-model','model_options':{'max_output_tokens':12000,'timeout_seconds':150}})
        with patch.dict('os.environ',{'MODEL_API_KEY':'fake-env-key'}):
            config=manager.model_configuration();provider=manager.model_provider()
            self.assertEqual(config['credential_source'],'environment');self.assertEqual(config['settings_source'],'saved_connector')
            self.assertEqual(provider.request_options('work')['max_tokens'],12000)
            self.assertEqual(provider.request_options('work')['timeout'],150)
            self.assertEqual(config['request_policy']['max_output_tokens'],12000)
    def test_invalid_limits_fail_before_saving_without_echoing_value(self):
        for limits in [{'max_output_tokens':999999},{'timeout_seconds':0},{'timeout_seconds':True}]:
            with self.assertRaises(ValueError):self.console.connectors.save({'kind':'meta','name':'Bad limits','model_options':limits})
        self.assertEqual(self.console.connectors.list(),[])
    def test_loopback_wire_checks_keep_explicit_short_timeouts(self):
        from collective101.provider import MetaProvider
        provider=MetaProvider(api_key='simulation-only',base_url='http://127.0.0.1:4010/meta/v1',timeout=.15)
        self.assertEqual(provider.request_options('work')['timeout'],.15)
