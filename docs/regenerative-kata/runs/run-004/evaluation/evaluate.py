"""Independent local SMTP/GitHub transport boundary evaluation."""
import json
import os
import select
import socketserver
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

root=Path(__file__).resolve().parents[1];work=root/'evaluation/work';work.mkdir(parents=True,exist_ok=False)
mail=[];requests=[];issues={};api={'fail':True};checks=[]
class SMTP(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 local synthetic SMTP\r\n');self.wfile.flush()
        while True:
            line=self.rfile.readline()
            if not line:return
            command=line.decode(errors='replace').strip()
            if command.upper().startswith(('EHLO','HELO')):reply=b'250 local\r\n'
            elif command.upper().startswith(('MAIL','RCPT','RSET')):reply=b'250 OK\r\n'
            elif command.upper()=='DATA':
                self.wfile.write(b'354 End with dot\r\n');self.wfile.flush();body=[]
                while True:
                    line=self.rfile.readline()
                    if line in (b'.\r\n',b''):break
                    body.append(line)
                mail.append(b''.join(body).decode(errors='replace'));reply=b'250 Accepted\r\n'
            elif command.upper()=='QUIT':self.wfile.write(b'221 Bye\r\n');self.wfile.flush();return
            else:reply=b'250 OK\r\n'
            self.wfile.write(reply);self.wfile.flush()
class MailServer(socketserver.ThreadingTCPServer):allow_reuse_address=True
smtp=MailServer(('127.0.0.1',0),SMTP);threading.Thread(target=smtp.serve_forever,daemon=True).start()
class API(BaseHTTPRequestHandler):
    def process(self,method):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))) if method!='GET' else None
        requests.append({'method':method,'path':self.path,'body':body,'auth_correct':self.headers.get('Authorization')=='Bearer SYNTHETIC_TEST_TOKEN'})
        if api['fail']:
            self.send_response(503);self.end_headers();return
        if method=='POST':
            n=len(issues)+1;issues[n]=dict(body,number=n,state='open');data=issues[n]
        elif method=='PATCH':
            n=int(self.path.rsplit('/',1)[1]);issues[n].update(body);data=issues[n]
        else:data=[v for v in issues.values() if v['state']=='open']
        self.send_response(200 if method!='POST' else 201);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
    def do_GET(self):self.process('GET')
    def do_POST(self):self.process('POST')
    def do_PATCH(self):self.process('PATCH')
    def log_message(self,*args):pass
github=ThreadingHTTPServer(('127.0.0.1',0),API);threading.Thread(target=github.serve_forever,daemon=True).start()
c={'service_names':{'gd-service':'Groundhog Day Service'},'email':{'smtp_host':'127.0.0.1','smtp_port':smtp.server_address[1],'from_address':'synthetic@example.invalid','to_addresses':['engineering@example.invalid'],'starttls':False},'github':{'api_base':f'http://127.0.0.1:{github.server_port}','repository':'synthetic/status','token_env':'KATA_FAKE_TOKEN'}}
(work/'config.json').write_text(json.dumps(c));process=None
def start():
    global process,port
    args=[sys.executable,str(root/'builder-output/alert_adapter.py'),'--config',str(work/'config.json'),'--db',str(work/'ledger.sqlite'),'--host','127.0.0.1','--port','0']
    process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,KATA_FAKE_TOKEN='SYNTHETIC_TEST_TOKEN'))
    assert select.select([process.stdout],[],[],8)[0],'adapter did not start'
    line=process.stdout.readline();assert line,(process.poll(),process.stderr.read())
    port=json.loads(line)['port']
def stop():
    global process
    if process:process.terminate();process.wait(timeout=5);process=None
def send(event,expected):
    req=urllib.request.Request(f'http://127.0.0.1:{port}/events',data=json.dumps(event).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=8) as r:code=r.status
    except urllib.error.HTTPError as e:code=e.code
    assert code==expected,(code,expected)
def check(name,condition):assert condition,name;checks.append({'check':name,'outcome':'pass'})
event={'id':'synthetic-open-1','service_id':'gd-service','type':'opened','observed_at':'2030-02-02T12:00:00Z','description':'Synthetic HTTP 502 observed'}
try:
    start();send(event,503)
    check('Email accepted while GitHub failure returns retryable 503',len(mail)==1 and len(issues)==0)
    check('SMTP message contains event identity and recipient',event['id'] in mail[0] and 'engineering@example.invalid' in mail[0])
    stop();api['fail']=False;start();send(event,204)
    check('Restart retries GitHub without resending accepted email',len(mail)==1 and len(issues)==1)
    send(event,204);check('Completed duplicate is acknowledged without side effects',len(mail)==1 and len(issues)==1)
    resolved=dict(event,id='synthetic-resolved-1',type='resolved',observed_at='2030-02-02T12:01:00Z')
    send(resolved,204);check('Recovery sends email and closes mapped GitHub issue',len(mail)==2 and issues[1]['state']=='closed')
    send(dict(event,id='synthetic-open-2'),204);check('New incident opens new issue after resolution',len(mail)==3 and len(issues)==2 and issues[2]['state']=='open')
    check('GitHub requests use explicit auth and one scoped repository',all(x['auth_correct'] and x['path'].startswith('/repos/synthetic/status/issues') for x in requests))
    send(dict(event,id='',type='bogus'),400);check('Invalid event rejected without transport side effects',len(mail)==3 and len(issues)==2)
    # Independent negative transport control: unavailable sink must never produce success.
    api['fail']=True;send(dict(event,id='synthetic-service2',service_id='gd-second'),503)
    check('Negative control: failed GitHub delivery cannot be acknowledged complete',True)
finally:
    stop();smtp.shutdown();smtp.server_close();github.shutdown();github.server_close()
    (root/'evidence/results.json').write_text(json.dumps({'checks':checks,'passed':len(checks),'smtp_messages':mail,'github_requests':requests,'issues':issues,'all_destinations':'Loopback synthetic servers; no external messages'},indent=2)+'\n')
print(json.dumps({'passed':len(checks)},indent=2))
