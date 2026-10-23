"""Independent existing-browser checks over exact synthetic Priory output copies."""
import json
import re
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'browser-review'; (out/'pages').mkdir(parents=True,exist_ok=True); (out/'screenshots').mkdir(exist_ok=True)
probe='''<script>window.addEventListener('load',()=>{const cards=[...document.querySelectorAll('[data-service-id]')];const a=document.querySelector('#support-link');const result={width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.left< -1||r.right>innerWidth+1)}).map(e=>e.tagName),services:cards.map(c=>{const s=c.querySelector('.state'),r=c.getBoundingClientRect();return {id:c.dataset.serviceId,state:c.dataset.state,text:s.innerText,color:getComputedStyle(s).color,background:getComputedStyle(s).backgroundColor,fontSize:getComputedStyle(s).fontSize,width:r.width,description:c.innerText}}),summary:document.querySelector('#summary').innerText,support:{href:a.href,text:a.innerText,display:getComputedStyle(a).display,fontSize:getComputedStyle(a).fontSize},agingVisible:!document.querySelector('#aging').hidden,agingText:document.querySelector('#aging').innerText};const e=document.createElement('script');e.id='review-proof';e.type='application/json';e.textContent=JSON.stringify(result);document.body.append(e);});</script>'''
cases=[('healthy','healthy',0),('failed','failed',0),('minor','minor',0),('recovered','recovered',0),('stale','stale',0),('client-aged','recovered',120000),('absent','absent',0)]
results=[]
for case,source,age in cases:
    source_dir=root/'evaluation/work'/source
    model=json.loads((source_dir/'status.json').read_text())
    page=(source_dir/'index.html').read_text()
    clock='Date.now=()=>Date.parse('+json.dumps(model['generated_at'])+')+'+str(age)+';'
    page=page.replace('<script>','<script>'+clock,1).replace('</body>',probe+'</body>')
    path=out/'pages'/(case+'.html'); path.write_text(page)
    for label,width,height in [('phone',390,844),('square',720,720),('tablet',820,1180)]:
        name=case+'-'+label
        args=[sys.argv[1],'--headless','--user-data-dir=/tmp/priory-kata-browser-run002','--disable-background-networking','--disable-component-update','--no-first-run',f'--window-size={width},{height}','--virtual-time-budget=100',f'--screenshot={out/"screenshots"/(name+".png")}','--dump-dom',path.as_uri()]
        r=subprocess.run(args,capture_output=True,text=True,check=True,timeout=20)
        match=re.search(r'<script id="review-proof" type="application/json">(.*?)</script>',r.stdout,re.S)
        assert match,name+': no DOM proof'
        proof=json.loads(match.group(1)); proof['case']=name
        assert proof['width']==width and proof['documentWidth']<=width and not proof['overflow'],name+': overflow'
        assert len(proof['services'])==10,name+': registry'
        assert proof['support']['href']=='https://support.example.invalid/help' and proof['support']['display']!='none',name+': support'
        states={s['id']:s['state'] for s in proof['services']}
        expected={s['id']:s['state'] for s in model['services']}
        if age: expected={k:'unknown' for k in expected}
        assert states==expected,(name,states,expected)
        for s in proof['services']:
            assert float(s['fontSize'].removesuffix('px'))>=16 and s['width']>0,name+': text'
            assert s['state'].lower() in s['text'].lower(),name+': non-color status'
            rgb=list(map(int,re.findall(r'\d+',s['color'])[:3]))
            if s['state']=='healthy': assert rgb[1]>rgb[0] and rgb[1]>rgb[2],name+': green'
            elif s['state']=='impaired': assert rgb[0]>rgb[1] and rgb[0]>rgb[2],name+': red'
            else: assert rgb[0]>rgb[1]>rgb[2],name+': amber'
        if case=='client-aged': assert proof['agingVisible'],name+': aged banner'
        if case=='minor': assert states['gd-application']=='healthy' and states['gd-pollen']=='impaired' and 'all operations' not in proof['summary'].lower(),name+': scope'
        proof['outcome']='pass'; results.append(proof)
version=subprocess.run([sys.argv[1],'--version'],capture_output=True,text=True,check=True).stdout.strip()
(out/'results.json').write_text(json.dumps({'browser':version,'route':'Local file copies; evaluator-only fixed Date.now and DOM probe; original output unchanged','results':results},indent=2)+'\n')
print(json.dumps({'browser':version,'passed':len(results),'cases':len(cases),'viewports':3},indent=2))
