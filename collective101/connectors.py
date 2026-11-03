"""User-configured connector registry, secret storage and current agent access."""
import hashlib,json,os,re,uuid
from .store import encode,now
from .secret_vault import SecretVault
from .mcp_client import MCPClient,endpoint_parts
from .registry import DEPARTMENT_MAP
from .provider import request_policy
from urllib.parse import urlsplit

SCHEMA='''CREATE TABLE IF NOT EXISTS connector_configs(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,name TEXT NOT NULL,url TEXT NOT NULL,model TEXT NOT NULL,
 secret TEXT NOT NULL,enabled INTEGER NOT NULL,departments TEXT NOT NULL,tools TEXT NOT NULL,
 selected TEXT NOT NULL,allow_local INTEGER NOT NULL,error TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS org_connector_bindings(run_id TEXT NOT NULL,tool_key TEXT NOT NULL,fingerprint TEXT NOT NULL,
 PRIMARY KEY(run_id,tool_key));'''

def redact(value,secret):
    if not secret:return value
    if isinstance(value,str):return value.replace(secret,'[REDACTED]')
    if isinstance(value,list):return [redact(v,secret) for v in value]
    if isinstance(value,dict):return {redact(k,secret):redact(v,secret) for k,v in value.items()}
    return value

def is_connector_tool(name):return isinstance(name,str) and bool(re.fullmatch(r'mcp_[a-f0-9]{12}_[a-f0-9]{12}',name))

class ConnectorManager:
    def __init__(self,store,roster):
        self.store,self.roster,self.vault=store,roster,SecretVault()
        with store.transaction() as db:
            db.executescript(SCHEMA)
            if 'model_options' not in {r[1] for r in db.execute('PRAGMA table_info(connector_configs)')}:
                db.execute("ALTER TABLE connector_configs ADD COLUMN model_options TEXT NOT NULL DEFAULT '{}'")
            # The workspace owner now connects tools for the whole organization.
            # Updating legacy scope also invalidates existing mission fingerprints.
            scope=encode(sorted(DEPARTMENT_MAP))
            db.execute('UPDATE connector_configs SET departments=? WHERE departments<>?',(scope,scope))
    def _rows(self):
        rows=self.store.query('SELECT * FROM connector_configs ORDER BY kind,name')
        for row in rows:
            for field in ('departments','tools','selected','model_options'):row[field]=json.loads(row[field])
        return rows
    def _get(self,cid):
        rows=[r for r in self._rows() if r['id']==cid]
        if not rows:raise ValueError('Unknown connector')
        return rows[0]
    def public(self,row):
        return {k:v for k,v in row.items() if k!='secret'}|{'has_secret':bool(row['secret']), 'enabled':bool(row['enabled'])}
    def list(self):return [self.public(r) for r in self._rows()]
    def secret(self,cid):return self.vault.reveal(self._get(cid)['secret'])
    def save(self,data):
        if not isinstance(data,dict):raise ValueError('Connector settings must be an object')
        kind=data.get('kind')
        if kind not in {'meta','brave','mcp'}:raise ValueError('Choose Meta, Brave Search or remote MCP')
        cid=data.get('id') or ('model' if kind=='meta' else 'brave' if kind=='brave' else uuid.uuid4().hex[:12])
        old=next((r for r in self._rows() if r['id']==cid),None)
        if old and old['kind']!=kind:raise ValueError('Connector kind cannot change')
        if kind=='mcp' and not re.fullmatch('[a-f0-9]{12}',cid):raise ValueError('Invalid connector identifier')
        if kind=='meta' and cid!='model' or kind=='brave' and cid!='brave':raise ValueError('Invalid built-in connector identifier')
        name=data.get('name',kind)
        if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Enter a connector name')
        local=data.get('allow_local',False)
        if type(local) is not bool:raise ValueError('Invalid local-server setting')
        url=data.get('url','https://api.meta.ai/v1' if kind=='meta' else '')
        if kind in {'meta','mcp'}:endpoint_parts(url,local if kind=='mcp' else False)
        departments=sorted(DEPARTMENT_MAP)
        value=data.get('secret','')
        if not isinstance(value,str) or len(value)>4096 or any(c in value for c in '\r\n'):raise ValueError('Invalid credential')
        secret=self.vault.seal(value) if value else old['secret'] if old else ''
        model=data.get('model','')
        if not isinstance(model,str) or len(model)>200:raise ValueError('Invalid model name')
        options=data.get('model_options',old['model_options'] if old else {}) if kind=='meta' else {}
        if not isinstance(options,dict) or set(options)-{'max_output_tokens','timeout_seconds','temperature'}:
            raise ValueError('Invalid model request settings')
        if kind=='meta':request_policy(options.get('max_output_tokens'),options.get('timeout_seconds'),options.get('temperature'))
        # Changing configuration revokes tool selections until explicitly enabled again.
        enabled=int(kind=='meta')
        tools=[];selected=[]
        self.store.execute('''INSERT INTO connector_configs(id,kind,name,url,model,secret,enabled,departments,tools,selected,allow_local,error,updated_at,model_options) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url,model=excluded.model,secret=excluded.secret,
            enabled=excluded.enabled,departments=excluded.departments,tools=excluded.tools,selected=excluded.selected,
            allow_local=excluded.allow_local,error=NULL,updated_at=excluded.updated_at,model_options=excluded.model_options''',
            (cid,kind,name,url,model,secret,enabled,encode(departments),encode(tools),encode(selected),int(local),None,now(),encode(options)))
        return self.public(self._get(cid))
    def model_ready(self):
        return self.model_configuration()['configured']
    def model_configuration(self):
        """Presence/provenance only; never decrypt a key for health or UI display."""
        row=next((r for r in self._rows() if r['kind']=='meta'),None)
        source='saved_connector' if row and row['secret'] else 'environment' if os.environ.get('MODEL_API_KEY') else 'none'
        enabled=bool(row['enabled']) if row else True
        options=row['model_options'] if row else {}
        result={'configured':enabled and source!='none','enabled':enabled,'credential_source':source,
                'settings_source':'saved_connector' if row else 'environment_defaults',
                'model':(row['model'] if row else '') or os.environ.get('META_MODEL') or 'muse-spark-1.3',
                'endpoint_host':urlsplit(row['url'] if row else 'https://api.meta.ai/v1').hostname,
                'connection_verified':False}
        try:result['request_policy']=request_policy(options.get('max_output_tokens'),options.get('timeout_seconds'),options.get('temperature'))
        except ValueError as error:result.update(configured=False,error=str(error),request_policy={})
        return result
    def model_provider(self):
        from .provider import MetaProvider
        row=next((r for r in self._rows() if r['kind']=='meta'),None)
        if row and not row['enabled']:raise ValueError('Live model disconnected. Configure it in Connectors.')
        configuration=self.model_configuration()
        if configuration.get('error'):raise ValueError(configuration['error'])
        if not self.model_ready():raise ValueError('Live chat requires a model connection in Connectors or MODEL_API_KEY; no response was generated.')
        return MetaProvider(api_key=self.vault.reveal(row['secret']) if row and row['secret'] else None,
            base_url=row['url'] if row else 'https://api.meta.ai/v1',model=(row['model'] or None) if row else None,
            max_output_tokens=configuration['request_policy']['max_output_tokens'],timeout=configuration['request_policy']['timeout_seconds'],temperature=configuration['request_policy']['temperature'])
    def brave_access(self,agent_id):
        row=next((r for r in self._rows() if r['kind']=='brave'),None)
        return agent_id in self.roster and (not row or bool(row['enabled']))
    def brave_ready(self,agent_id=None):
        row=next((r for r in self._rows() if r['kind']=='brave'),None)
        if row:
            return bool(row['enabled'] and (row['secret'] or os.environ.get('BRAVE_SEARCH_API_KEY')) and
                (agent_id is None or agent_id in self.roster))
        return bool(os.environ.get('BRAVE_SEARCH_API_KEY'))
    def brave_secret(self):
        row=next((r for r in self._rows() if r['kind']=='brave'),None)
        if row and not row['enabled']:return ''
        return self.vault.reveal(row['secret']) if row and row['secret'] else os.environ.get('BRAVE_SEARCH_API_KEY','')
    def discover(self,cid):
        row=self._get(cid)
        if row['kind']!='mcp':raise ValueError('Discovery is for remote MCP servers')
        # Refresh revokes previous selections even if discovery fails.
        self.disable(cid)
        try:
            raw=MCPClient(row['url'],self.vault.reveal(row['secret']),bool(row['allow_local'])).tools()
            secret=self.vault.reveal(row['secret'])
            if secret:raw=redact(raw,secret)
            tools=[];seen=set()
            for item in raw:
                name=item.get('name')
                if not isinstance(name,str) or not name or len(name)>200 or name in seen:raise ValueError('Invalid or duplicate MCP tool name')
                schema=item.get('inputSchema')
                if not isinstance(schema,dict) or len(encode(schema))>12000:raise ValueError('Unsupported MCP tool schema size')
                annotation=item.get('annotations',{})
                readonly=isinstance(annotation,dict) and annotation.get('readOnlyHint') is True and annotation.get('destructiveHint') is not True
                tools.append({'key':'mcp_'+cid+'_'+hashlib.sha256(name.encode()).hexdigest()[:12], 'name':name,
                    'description':str(item.get('description',''))[:2000],'inputSchema':schema,'read_only':readonly})
                seen.add(name)
            with self.store.transaction() as db:
                changed=db.execute('UPDATE connector_configs SET tools=?,selected=?,enabled=0,error=NULL,updated_at=? WHERE id=? AND url=? AND secret=? AND allow_local=?',
                    (encode(tools),'[]',now(),cid,row['url'],row['secret'],row['allow_local'])).rowcount
                if not changed:raise ValueError('Connector settings changed during discovery; discover again')
        except Exception as error:
            self.store.execute("UPDATE connector_configs SET error='Discovery failed; check URL, authentication and supported transport' WHERE id=?",(cid,))
            raise ValueError('MCP discovery failed. Check URL, authentication, network access and supported transport.') from None
        return self.public(self._get(cid))
    def enable(self,cid,selected,departments=None):
        # Legacy clients may send departments; connection scope is always global.
        row=self._get(cid);departments=sorted(DEPARTMENT_MAP)
        if not isinstance(selected,list) or not selected or len(set(selected))!=len(selected):raise ValueError('Select the tools to enable')
        allowed={t['key'] for t in row['tools'] if t['read_only']} if row['kind']=='mcp' else {'web_search'} if row['kind']=='brave' else set()
        if set(selected)-allowed:raise ValueError('Only discovered read-only tools can be enabled; unknown or write tools are unavailable')
        if row['kind']=='brave' and not(row['secret'] or os.environ.get('BRAVE_SEARCH_API_KEY')):raise ValueError('Enter a search credential first')
        self.store.execute('UPDATE connector_configs SET enabled=1,selected=?,departments=?,error=NULL,updated_at=? WHERE id=?',(encode(selected),encode(departments),now(),cid))
        return self.public(self._get(cid))
    def disable(self,cid):
        self._get(cid);self.store.execute('UPDATE connector_configs SET enabled=0,updated_at=? WHERE id=?',(now(),cid))
        return self.public(self._get(cid))
    def catalog(self,agent_id=None):
        items=[]
        for row in self._rows():
            if row['kind']!='mcp' or not row['enabled']:continue
            if agent_id is not None and agent_id not in self.roster:continue
            for tool in row['tools']:
                if tool['key'] in row['selected'] and tool['read_only']:
                    items.append({'name':tool['key'],'title':row['name']+' / '+tool['name'],'description':tool['description'],
                        'arguments':tool['inputSchema'],'available':True,'scope':'Organization-wide; available to all agents within mission and task permissions'})
        return items
    def fingerprint(self,key):
        for row in self._rows():
            if any(t['key']==key for t in row['tools']):
                return hashlib.sha256(encode({k:row[k] for k in ('url','secret','tools','selected','departments','enabled')}).encode()).hexdigest()
        return None
    def bind(self,run_id,capabilities):
        for key in capabilities:
            if is_connector_tool(key):
                fingerprint=self.fingerprint(key)
                if not fingerprint or key not in {t['name'] for t in self.catalog()}:raise ValueError('Mission names an unavailable connector tool')
                self.store.execute('INSERT INTO org_connector_bindings VALUES(?,?,?)',(run_id,key,fingerprint))
    def call(self,key,args,agent_id,run_id=None):
        if key not in {t['name'] for t in self.catalog(agent_id)}:return {'status':'unavailable','error':'Connector disconnected or access revoked'}
        if run_id:
            rows=self.store.query('SELECT fingerprint FROM org_connector_bindings WHERE run_id=? AND tool_key=?',(run_id,key))
            if not rows or rows[0]['fingerprint']!=self.fingerprint(key):return {'status':'denied','error':'Connector configuration changed; start a new mission'}
        for row in self._rows():
            for tool in row['tools']:
                if tool['key']==key:
                    if not isinstance(args,dict) or len(encode(args))>40000:raise ValueError('Invalid connector arguments')
                    if any(field not in args for field in tool['inputSchema'].get('required',[])):raise ValueError('Required connector arguments are missing')
                    # Server validates the complete advertised JSON Schema; no remote refs are loaded locally.
                    result=MCPClient(row['url'],self.vault.reveal(row['secret']),bool(row['allow_local'])).call(tool['name'],args)
                    # Never persist a reflected authentication token from a remote response.
                    secret=self.vault.reveal(row['secret'])
                    encoded=encode(redact(result,secret))
                    if len(encoded)>64000:return {'status':'failed','error':'Connector output exceeds bounds'}
                    return json.loads(encoded)
        return {'status':'unavailable','error':'Connector tool not found'}
