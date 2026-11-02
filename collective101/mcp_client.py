"""Bounded MCP Streamable HTTP client; URLs are operator-configured, never agent-supplied."""
import http.client,ipaddress,json,socket,ssl,time,urllib.parse

VERSIONS={'2025-06-18','2025-03-26','2025-11-25'}

def endpoint_parts(url,allow_local=False):
    if not isinstance(url,str) or len(url)>2000:raise ValueError('Invalid connector URL')
    value=urllib.parse.urlsplit(url)
    if value.username or value.password or value.query or value.fragment or not value.hostname:
        raise ValueError('Use a connector URL without embedded credentials, query or fragment')
    local=value.hostname in {'127.0.0.1','localhost','::1'}
    if value.scheme!='https' and not(value.scheme=='http' and local and allow_local):
        raise ValueError('Use HTTPS; explicit local-server access allows loopback HTTP only')
    if local and not allow_local:raise ValueError('Local server access must be explicitly enabled')
    try:port=value.port or (443 if value.scheme=='https' else 80)
    except ValueError:raise ValueError('Invalid connector port') from None
    return value,port


def exchange(url,payload,headers,allow_local=False):
    parsed,port=endpoint_parts(url,allow_local)
    resolved=socket.getaddrinfo(parsed.hostname,port,type=socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(row[4][0] for row in resolved))
    if not addresses:raise ValueError('Connector address could not be resolved')
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if not(ip.is_global or (allow_local and ip.is_loopback)):
            raise ValueError('Private, metadata and link-local connector destinations are not allowed')
    # Pin this connection to the validated address; TLS still authenticates the original hostname.
    address=addresses[0]
    class PinnedHTTP(http.client.HTTPConnection):
        def connect(self):self.sock=socket.create_connection((address,port),timeout=10)
    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            raw=socket.create_connection((address,port),timeout=10)
            try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
            except Exception:raw.close();raise
    connection=(PinnedHTTPS if parsed.scheme=='https' else PinnedHTTP)(parsed.hostname,port,timeout=10)
    try:
        connection.request('POST',parsed.path or '/',body=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream',**headers})
        response=connection.getresponse()
        if response.status==202 and 'id' not in payload:return {},dict(response.getheaders())
        if response.status!=200:raise ValueError('Connector request failed (HTTP '+str(response.status)+')')
        if response.getheader('Content-Type','').split(';')[0].strip()=='text/event-stream':
            started=time.monotonic();size=0;data=[]
            while time.monotonic()-started<20:
                line=response.readline(65537);size+=len(line)
                if size>262144:raise ValueError('Connector stream exceeds bounds')
                if not line:break
                if line.startswith(b'data:'):data.append(line[5:].strip())
                if not line.strip() and data:
                    message=json.loads(b'\n'.join(data));data=[]
                    if message.get('id')==payload.get('id'):return message,dict(response.getheaders())
            raise ValueError('Connector stream did not return the requested result')
        raw=response.read(262145)
        if len(raw)>262144:raise ValueError('Connector response exceeds bounds')
        return json.loads(raw),dict(response.getheaders())
    except (OSError,UnicodeError,json.JSONDecodeError,http.client.HTTPException):
        raise ValueError('Connector connection failed or returned an invalid response') from None
    finally:connection.close()

class MCPClient:
    def __init__(self,url,secret='',allow_local=False):
        self.url,self.secret,self.allow_local=url,secret,allow_local
        self.sequence=0;self.session=None;self.version='2025-06-18'
    def request(self,method,params=None,notification=False):
        payload={'jsonrpc':'2.0','method':method}
        if params is not None:payload['params']=params
        if not notification:self.sequence+=1;payload['id']=self.sequence
        headers={'MCP-Protocol-Version':self.version}
        if self.secret:headers['Authorization']='Bearer '+self.secret
        if self.session:headers['Mcp-Session-Id']=self.session
        value,returned=exchange(self.url,payload,headers,self.allow_local)
        sid=next((v for k,v in returned.items() if k.lower()=='mcp-session-id'),None)
        if sid:
            if len(sid)>512 or any(ord(c)<33 or ord(c)>126 for c in sid):raise ValueError('Invalid MCP session identifier')
            self.session=sid
        if notification:return None
        if not isinstance(value,dict) or value.get('jsonrpc')!='2.0' or value.get('id')!=self.sequence or 'error' in value or 'result' not in value:
            raise ValueError('MCP server rejected the request or returned a mismatched response')
        return value['result']
    def initialize(self):
        result=self.request('initialize',{'protocolVersion':self.version,'capabilities':{},'clientInfo':{'name':'collective101','version':'0.3'}})
        if not isinstance(result,dict) or result.get('protocolVersion') not in VERSIONS or 'tools' not in result.get('capabilities',{}):
            raise ValueError('Unsupported MCP version or missing tools capability')
        self.version=result['protocolVersion'];self.request('notifications/initialized',notification=True)
    def tools(self):
        self.initialize();items=[];cursor=None;seen=set()
        for _ in range(10):
            result=self.request('tools/list',{'cursor':cursor} if cursor else {})
            if not isinstance(result,dict) or not isinstance(result.get('tools'),list):raise ValueError('Invalid MCP tools list')
            items.extend(result['tools'])
            if len(items)>50:raise ValueError('Connector exposes more than the supported 50 tools')
            cursor=result.get('nextCursor')
            if not cursor:return items
            if not isinstance(cursor,str) or len(cursor)>2000 or cursor in seen:raise ValueError('Invalid MCP pagination cursor')
            seen.add(cursor)
        raise ValueError('MCP pagination limit exceeded')
    def call(self,name,arguments):
        self.initialize()
        result=self.request('tools/call',{'name':name,'arguments':arguments})
        if not isinstance(result,dict):raise ValueError('Invalid MCP tool result')
        # Never load remote resources, images, links or executable instructions from the result.
        contents=[{'type':'text','text':str(item.get('text',''))[:12000]} for item in result.get('content',[])[:8] if isinstance(item,dict) and item.get('type')=='text']
        return {'status':'failed' if result.get('isError') else 'ok','content':contents,'structuredContent':result.get('structuredContent'),'source':'MCP tool result; untrusted external data'}
