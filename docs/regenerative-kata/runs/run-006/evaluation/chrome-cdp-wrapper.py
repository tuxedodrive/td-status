#!/opt/homebrew/bin/python3
import sys,subprocess,tempfile,pathlib,time,json,urllib.request,socket,base64,os,struct,re
chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
args=sys.argv[1:]
if '--version' in args:
 subprocess.run([chrome,'--version']);sys.exit()
w,h=map(int,next(a.split('=',1)[1] for a in args if a.startswith('--window-size=')).split(','))
budget=int(next(a.split('=',1)[1] for a in args if a.startswith('--virtual-time-budget=')))
url=args[-1]; profile=tempfile.mkdtemp(prefix='run006-cdp-')
p=subprocess.Popen([chrome,'--headless','--remote-debugging-port=0','--user-data-dir='+profile,'--disable-background-networking','--disable-component-update','--no-first-run','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
s=None
try:
 portfile=pathlib.Path(profile)/'DevToolsActivePort'
 for _ in range(100):
  if portfile.exists():break
  time.sleep(.05)
 port=int(portfile.read_text().splitlines()[0])
 targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))
 from urllib.parse import urlsplit
 u=urlsplit(next(x['webSocketDebuggerUrl'] for x in targets if x['type']=='page'))
 s=socket.create_connection((u.hostname,u.port));s.settimeout(30)
 key=base64.b64encode(os.urandom(16)).decode();s.sendall(f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
 header=b''
 while not header.endswith(b'\r\n\r\n'):header+=s.recv(1)
 assert b'101' in header,header
 def exact(n):
  b=b''
  while len(b)<n:b+=s.recv(n-len(b))
  return b
 def receive():
  a,b=exact(2);n=b&127
  if n==126:n=struct.unpack('!H',exact(2))[0]
  if n==127:n=struct.unpack('!Q',exact(8))[0]
  mask=exact(4) if b&128 else None;d=exact(n)
  if mask:d=bytes(x^mask[i%4] for i,x in enumerate(d))
  return json.loads(d)
 seq=0
 def call(method,params={}):
  global seq
  seq+=1;idx=seq;data=json.dumps({'id':idx,'method':method,'params':params}).encode();mask=os.urandom(4);n=len(data)
  length=bytes([128+n]) if n<126 else bytes([254])+struct.pack('!H',n) if n<65536 else bytes([255])+struct.pack('!Q',n)
  s.sendall(b'\x81'+length+mask+bytes(x^mask[i%4] for i,x in enumerate(data)))
  while True:
   m=receive()
   if m.get('id')==idx:
    assert 'error' not in m,m
    return m.get('result',{})
 call('Page.enable');call('Runtime.enable');call('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False})
 call('Emulation.setVirtualTimePolicy',{'policy':'pause'})
 call('Page.navigate',{'url':url})
 call('Emulation.setVirtualTimePolicy',{'policy':'pauseIfNetworkFetchesPending','budget':budget,'waitForNavigation':True})
 while True:
  event=receive()
  if event.get('method')=='Emulation.virtualTimeBudgetExpired':break
 dom=call('Runtime.evaluate',{'expression':'document.documentElement.outerHTML','returnByValue':True})['result']['value']
 for a in args:
  if a.startswith('--screenshot='):
   dest=pathlib.Path(a.split('=',1)[1]);dest.write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']))
 print(dom)
finally:
 if s:s.close()
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
