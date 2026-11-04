"""Local membership/session security with disposable state; no real credentials."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from collective101.accounts import AccountManager
from collective101.store import Store

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='fixture-only-password-123'


class AccountTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'work/account-tests';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.store=Store(Path(self.temp.name)/'state.db');self.accounts=AccountManager(self.store)

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def owner(self):
        token=self.accounts.register({'name':'Fixture Owner','username':'owner','password':PASSWORD})
        return token,self.accounts.user(token)

    def test_owner_bootstrap_invited_members_and_single_use_invitation(self):
        self.assertFalse(self.accounts.configured());token,owner=self.owner()
        self.assertEqual(owner['role'],'owner');self.assertNotIn('password_hash',owner)
        with self.assertRaisesRegex(ValueError,'invitation'):
            self.accounts.register({'name':'Stranger','username':'stranger','password':PASSWORD})
        invite=self.accounts.invite(owner)['code']
        member_token=self.accounts.register({'name':'Member','username':'member','password':PASSWORD,'invite':invite,'role':'owner'})
        member=self.accounts.user(member_token);self.assertEqual(member['role'],'member')
        with self.assertRaises(ValueError):self.accounts.invite(member)
        with self.assertRaises(ValueError):self.accounts.register({'name':'Replay','username':'replay','password':PASSWORD,'invite':invite})
        rows=self.store.query('SELECT password_hash FROM console_accounts')
        self.assertNotEqual(rows[0]['password_hash'],rows[1]['password_hash'])
        self.assertTrue(all(PASSWORD not in row['password_hash'] for row in rows))
        serialized=json.dumps(self.store.query('SELECT * FROM console_account_sessions')+self.store.query('SELECT * FROM console_account_audit')+self.store.query('SELECT * FROM console_account_invites'))
        self.assertNotIn(token,serialized);self.assertNotIn(member_token,serialized);self.assertNotIn(invite,serialized);self.assertNotIn(PASSWORD,serialized)

    def test_login_rotation_expiry_and_password_change_revoke_sessions(self):
        token,owner=self.owner()
        with self.assertRaisesRegex(ValueError,'incorrect'):self.accounts.login({'username':'owner','password':'fixture-wrong-password'})
        with self.assertRaisesRegex(ValueError,'incorrect'):self.accounts.login({'username':'missing','password':PASSWORD})
        second=self.accounts.login({'username':'OWNER','password':PASSWORD},token)
        self.assertIsNone(self.accounts.user(token));self.assertEqual(self.accounts.user(second)['id'],owner['id'])
        third=self.accounts.session(owner['id'])
        updated=self.accounts.change_password(owner,{'current_password':PASSWORD,'password':'fixture-replacement-password'})
        self.assertIsNone(self.accounts.user(second));self.assertIsNone(self.accounts.user(third));self.assertIsNotNone(self.accounts.user(updated))
        self.assertFalse(self.accounts.valid_scope(self.accounts.digest(second)))
        self.accounts.logout(updated);self.assertIsNone(self.accounts.user(updated))
        final=self.accounts.login({'username':'owner','password':'fixture-replacement-password'})
        self.store.execute('UPDATE console_account_sessions SET expires=0')
        self.assertIsNone(self.accounts.user(final))

    def test_registration_race_cannot_create_two_owners(self):
        def create(index):
            try:return self.accounts.register({'name':'Owner','username':'owner'+str(index),'password':PASSWORD})
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:tokens=list(pool.map(create,range(2)))
        self.assertEqual(sum(token is not None for token in tokens),1)
        self.assertEqual(len(self.store.query("SELECT id FROM console_accounts WHERE role='owner'")),1)

    def test_rate_limits_invalid_names_and_session_caps(self):
        token,owner=self.owner()
        for name in ['', 'x\nname', '\ud800', 'x'*61]:
            with self.assertRaises(ValueError):self.accounts.profile(owner,{'name':name})
        with self.assertRaises(ValueError):self.accounts.password('\ud800'*12)
        self.accounts.profile(owner,{'name':'New Name'})
        self.assertEqual(self.accounts.user(token)['name'],'New Name')
        for _ in range(10):self.accounts.session(owner['id'])
        self.assertEqual(len(self.store.query('SELECT digest FROM console_account_sessions')),8)
        for _ in range(10):
            try:self.accounts.login({'username':'absent','password':'too-short'})
            except ValueError:pass
        with self.assertRaisesRegex(ValueError,'Too many'):self.accounts.login({'username':'absent','password':PASSWORD})
