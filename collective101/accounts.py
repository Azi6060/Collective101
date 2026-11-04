"""Local shared-workspace membership. Separate from organization-agent permissions."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections import defaultdict, deque


SESSION_SECONDS = 12 * 60 * 60


class AccountManager:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.attempts = defaultdict(deque)
        with store.transaction() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS console_accounts(
              id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
              password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS console_account_sessions(
              digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES console_accounts(id) ON DELETE CASCADE,
              expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS console_account_invites(
              digest TEXT PRIMARY KEY, expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS console_account_audit(
              seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, user_id TEXT, created_at INTEGER NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS console_one_owner ON console_accounts(role) WHERE role='owner';
            ''')

    def configured(self):
        return bool(self.store.query('SELECT id FROM console_accounts LIMIT 1'))

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def password(value):
        if not isinstance(value, str) or not 12 <= len(value) <= 128:
            raise ValueError('Use a password between 12 and 128 characters.')
        try:raw=value.encode()
        except UnicodeError:raise ValueError('Use valid Unicode characters in the password.') from None
        if len(raw)>512:raise ValueError('Password exceeds the byte limit.')
        return raw

    @staticmethod
    def clean_name(name):
        if not isinstance(name,str) or not 1<=len(name.strip())<=60 or any(unicodedata.category(c).startswith('C') for c in name):
            raise ValueError('Enter a display name of 1–60 characters without control characters.')
        return name.strip()

    @staticmethod
    def derive(value, salt):
        # OWASP's scrypt N=2^15, r=8, p=3 profile; no fast-hash fallback.
        return hashlib.scrypt(value, salt=salt, n=2**15, r=8, p=3, maxmem=64*1024*1024, dklen=32)

    def hash_password(self, password):
        salt = secrets.token_bytes(16)
        return salt.hex() + ':' + self.derive(self.password(password), salt).hex()

    def verify(self, password, stored=None):
        try:
            raw = self.password(password)
        except ValueError:
            return False
        salt, expected = stored.split(':') if stored else ('00'*16, '00'*32)
        actual = self.derive(raw, bytes.fromhex(salt))
        return hmac.compare_digest(actual, bytes.fromhex(expected)) and stored is not None

    def limited(self, username):
        stamp = time.monotonic()
        if len(self.attempts) > 1024:
            self.attempts = defaultdict(deque, {k:v for k,v in self.attempts.items() if v and v[-1] > stamp-300})
        for key, limit in [('all', 50), ('user:'+self.digest(str(username)[:128]), 10)]:
            queue = self.attempts[key]
            while queue and queue[0] < stamp-300:
                queue.popleft()
            if len(queue) >= limit:
                raise ValueError('Too many account attempts. Try again in five minutes.')
            queue.append(stamp)

    def audit(self, kind, user_id=None):
        self.store.execute('INSERT INTO console_account_audit(kind,user_id,created_at) VALUES(?,?,?)', (kind,user_id,int(time.time())))

    def user(self, token):
        if not isinstance(token, str) or len(token) > 100:
            return None
        rows = self.store.query('''SELECT a.id,a.username,a.name,a.role FROM console_accounts a
            JOIN console_account_sessions s ON s.user_id=a.id WHERE s.digest=? AND s.expires>?''',
            (self.digest(token), int(time.time())))
        return rows[0] if rows else None

    def valid_scope(self, digest):
        return bool(self.store.query('SELECT digest FROM console_account_sessions WHERE digest=? AND expires>?',(digest,int(time.time()))))

    def session(self, user_id):
        token = secrets.token_urlsafe(32)
        with self.store.transaction() as db:
            db.execute('DELETE FROM console_account_sessions WHERE expires<=?', (int(time.time()),))
            db.execute('INSERT INTO console_account_sessions VALUES(?,?,?)', (self.digest(token),user_id,int(time.time())+SESSION_SECONDS))
            # Bound sessions per identity; newest sessions remain valid.
            db.execute('''DELETE FROM console_account_sessions WHERE user_id=? AND digest NOT IN
                (SELECT digest FROM console_account_sessions WHERE user_id=? ORDER BY rowid DESC LIMIT 8)''',(user_id,user_id))
        return token

    def register(self, data):
        with self.lock:
            username = data.get('username','')
            self.limited(username)
            if not isinstance(username,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{2,31}',username):
                raise ValueError('Use a username of 3–32 letters, numbers, dots, underscores or hyphens.')
            name = self.clean_name(data.get('name'))
            first = not self.configured()
            invite = data.get('invite','')
            if not first and (not isinstance(invite,str) or len(invite)>100 or not self.store.query(
                'SELECT digest FROM console_account_invites WHERE digest=? AND used=0 AND expires>?',
                (self.digest(invite),int(time.time())))):
                raise ValueError('Ask the workspace owner for a valid invitation code.')
            hashed = self.hash_password(data.get('password'))
            uid = 'user_'+secrets.token_hex(12)
            try:
                with self.store.transaction() as db:
                    db.execute('INSERT INTO console_accounts VALUES(?,?,?,?,?,?)',
                        (uid,username.lower(),name.strip(),hashed,'owner' if first else 'member',int(time.time())))
                    if not first:
                        if db.execute('UPDATE console_account_invites SET used=1 WHERE digest=? AND used=0 AND expires>?',
                            (self.digest(invite),int(time.time()))).rowcount != 1:
                            raise ValueError('Invitation expired or already used.')
            except sqlite3.IntegrityError:
                raise ValueError('Unable to create this account. Check your username and invitation.') from None
            self.audit('registered',uid)
            return self.session(uid)

    def login(self, data, old_token=None):
        with self.lock:
            username = data.get('username','')
            self.limited(username)
            rows = self.store.query('SELECT id,password_hash FROM console_accounts WHERE username=?',
                (username.lower() if isinstance(username,str) else '',))
            if not self.verify(data.get('password'),rows[0]['password_hash'] if rows else None):
                self.audit('login_failed')
                raise ValueError('Username or password is incorrect.')
            if old_token:
                self.logout(old_token)
            self.audit('signed_in',rows[0]['id'])
            return self.session(rows[0]['id'])

    def logout(self, token):
        user = self.user(token)
        if token:
            self.store.execute('DELETE FROM console_account_sessions WHERE digest=?',(self.digest(token),))
        if user:
            self.audit('signed_out',user['id'])

    def invite(self, user):
        if not user or user['role'] != 'owner':
            raise ValueError('Only the workspace owner can create invitations.')
        with self.lock:
            self.store.execute('DELETE FROM console_account_invites WHERE used=1 OR expires<=?',(int(time.time()),))
            if len(self.store.query('SELECT digest FROM console_account_invites')) >= 20:
                raise ValueError('Twenty invitations are already pending.')
            token=secrets.token_urlsafe(18)
            self.store.execute('INSERT INTO console_account_invites VALUES(?,?,0)',(self.digest(token),int(time.time())+86400))
            self.audit('invitation_created',user['id'])
            return {'code':token,'expires_in':86400}

    def profile(self, user, data):
        if not user:raise ValueError('Sign in to continue.')
        name=self.clean_name(data.get('name'))
        self.store.execute('UPDATE console_accounts SET name=? WHERE id=?',(name.strip(),user['id']))
        self.audit('profile_updated',user['id'])

    def change_password(self, user, data):
        if not user:
            raise ValueError('Sign in to continue.')
        with self.lock:
            self.limited(user['username'])
            old=self.store.query('SELECT password_hash FROM console_accounts WHERE id=?',(user['id'],))[0]
            if not self.verify(data.get('current_password'),old['password_hash']):
                raise ValueError('Current password is incorrect.')
            hashed=self.hash_password(data.get('password'))
            with self.store.transaction() as db:
                db.execute('UPDATE console_accounts SET password_hash=? WHERE id=?',(hashed,user['id']))
                db.execute('DELETE FROM console_account_sessions WHERE user_id=?',(user['id'],))
            self.audit('password_changed',user['id'])
            return self.session(user['id'])
