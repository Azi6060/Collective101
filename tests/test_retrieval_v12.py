import sqlite3,tempfile,unittest
from pathlib import Path
from collective101.store import Store
from collective101 import retrieval
class RetrievalTests(unittest.TestCase):
 def test_hybrid_ranks_paraphrase_without_keyword_overlap(self):
  rows=[{'id':'a','content':'Reset your password to regain access to your account.'},{'id':'b','content':'Fresh apples and pears are delivered each morning.'}]
  ranked=retrieval.rank('forgot login credentials',rows)
  self.assertEqual(ranked[0]['id'],'a');self.assertEqual(ranked[0]['retrieval']['mode'],'hybrid');self.assertTrue(ranked[0]['retrieval']['semantic'])
 def test_empty_or_unrelated_memory_is_not_recentness_only_fallback(self):
  self.assertEqual(retrieval.rank('recover my account',[{'id':'b','content':'Fresh apples and pears are on the shelf.'}],minimum=.6),[])
 def test_changing_source_content_changes_cached_vector_identity(self):
  first=retrieval.rank('account access',[{'id':'a','content':'Reset your password to regain access.'}])[0]
  second=retrieval.rank('fruit',[{'id':'a','content':'Fresh apples and pears are fruits.'}])[0]
  self.assertNotEqual(first['retrieval']['content_hash'],second['retrieval']['content_hash'])
