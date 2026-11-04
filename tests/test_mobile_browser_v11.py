import unittest
from collective101.execution_adapters import execute_browser,validate_browser_checks
class MobileViewportTests(unittest.TestCase):
 def test_mobile_only_navigation_is_checked_at_declared_viewport(self):
  html='<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>#nav-toggle{display:none}@media(max-width:600px){#nav-toggle{display:block}}</style></head><body><button id="nav-toggle" onclick="document.getElementById(\'status\').textContent=\'Open\'">Menu</button><p id="status">Closed</p></body></html>'
  result=execute_browser([{'path':'index.html','content':html}],'index.html',[{'selector':'#nav-toggle','viewport':{'width':390,'height':844},'action':'click'},{'selector':'#status','equals':'Open'}])
  self.assertTrue(result['passed'],result);self.assertEqual(result['checks'][0]['viewport']['width'],390)
 def test_viewport_boundaries_reject_invalid_dimensions_and_extra_fields(self):
  for viewport in [{'width':True,'height':844},{'width':10,'height':844},{'width':390,'height':90000},{'width':390,'height':844,'url':'file:///secret'}]:
   with self.subTest(viewport=viewport),self.assertRaises(ValueError):validate_browser_checks([{'selector':'h1','visible':True,'viewport':viewport}])
