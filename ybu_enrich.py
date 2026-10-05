
import re, json, urllib.parse as up
import requests
from bs4 import BeautifulSoup
from datetime import date
TODAY=date.today().isoformat()
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36','Accept-Language':'en-US,en;q=0.9'}
BAD_DOM=('niche.com','greatschools','usnews','publicschoolreview','facebook','instagram','wikipedia','yelp','mapquest','schooldigger','nces.ed.gov','twitter','linkedin','youtube','zillow','maxpreps','bing.com','duckduckgo','google.com','x.com','privateschoolreview','citytowninfo','k12academics','schoolmap','ratemyteachers')
VENDORS=[('Jostens',r'jostens(yearbooks)?\.com|jostensyearbooks|yearbookavenue'),('Herff Jones',r'herffjones\.com|yearbookordercenter\.com|herff[\s-]?jones|yearbookdiscoveries'),('Walsworth',r'walsworth(yearbooks)?\.com|yearbookforever\.com|walsworth'),('TreeRing',r'treering\.com|tree\s?ring'),('Entourage',r'entourageyearbooks\.com|entourage\s+yearbooks'),('Balfour',r'balfour\.com|balfour\s+yearbooks?'),('Lifetouch/Shutterfly',r'ybpay\.lifetouch|lifetouch\.com|shutterfly\.com/yearbook'),('Strawbridge',r'strawbridge\.net'),('Pictavo',r'pictavo\.com'),('Inter-State Studio',r'inter-state\.com'),('School Annual',r'schoolannual\.com'),('Memory Book',r'memorybook\.com'),('YearbookLife',r'yearbooklife\.com'),('Picaboo',r'picaboo(yearbooks)?\.com')]
VEND_NAMES=['Jostens','Herff Jones','Walsworth','TreeRing','Entourage','Balfour','Lifetouch','Shutterfly','Strawbridge','Pictavo','Inter-State','School Annual','Memory Book','YearbookLife','Picaboo']
YB_LINK=re.compile(r'yearbook|year-book|publications|journalism|student\s*media',re.I)
STAFF_LINK=re.compile(r'staff|directory|faculty|our[-_ ]team|teachers|administration|administrators|about[-_ ]us|principal|contact',re.I)
EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
URL=re.compile(r'https?://[^\s\)\]\>"\']+')
NM=re.compile(r"^(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-zA-Z'\-]+){1,2})")
STOP={'high','school','h','s','hs','sr','senior','the','of','academy','charter','and','jr','junior','sch','community','public','regional','county','isd','district'}
S=requests.Session(); S.headers.update(UA)
def get(url,timeout=7):
    try:
        r=S.get(url,timeout=timeout,allow_redirects=True)
        if r.status_code<400 and 'html' in r.headers.get('content-type','html'): return r
    except Exception: pass
    return None
def domain(u):
    try: return up.urlsplit(u).netloc.lower().replace('www.','')
    except Exception: return ''
def keys(n): return [w for w in re.sub(r'[^a-z ]',' ',n.lower()).split() if w not in STOP and len(w)>2]
def resolve_site(r,web_search):
    site=r.WEBSITE if isinstance(r.WEBSITE,str) and r.WEBSITE.strip() else ''
    src='NCES CCD Directory'; status='missing'; resp=None
    if site:
        if not site.lower().startswith('http'): site='http://'+site
        resp=get(site)
        if resp is None: status='unreachable'
        else:
            t=BeautifulSoup(resp.text,'lxml').title; t=t.get_text() if t else ''
            path=up.urlsplit(resp.url).path.strip('/')
            hit=any(k in t.lower() or k in resp.url.lower() for k in keys(r.SCH_NAME))
            status='ok' if (hit or path) else 'district_root'
    if status!='ok':
        q=f'official school website for "{r.SCH_NAME}" high school in {r.LCITY}, {r.LSTATE} ({r.LEA_NAME}). Reply with the school homepage URL.'
        try:
            res,err=web_search(q)
            urls=[u.rstrip('.,);') for u in URL.findall(str(res)) if not any(b in u.lower() for b in BAD_DOM)]
        except Exception: urls=[]
        for u in urls[:2]:
            rr=get(u)
            if rr is not None:
                site=u; resp=rr; src={'missing':'Web search (NCES had no website) — Needs Verification','unreachable':'Web search (NCES URL unreachable) — Needs Verification','district_root':'Web search (NCES URL was district-level) — Needs Verification'}[status]; status='ok'; break
    return site,src,status,resp
def crawl(site,resp):
    soup=BeautifulSoup(resp.text,'lxml'); pages={resp.url:(soup,resp.text)}; base=domain(resp.url)
    links=[(up.urljoin(resp.url,a['href']),a.get_text(' ')+' '+a['href']) for a in soup.find_all('a',href=True)]
    yb=[h for h,t in links if YB_LINK.search(t)]; st=[h for h,t in links if STAFF_LINK.search(t)]
    root=base.split('.',1)[-1] if base.count('.')>=2 else base
    cand=[]
    for h in yb+st:
        if h not in cand and domain(h).endswith(root) and not re.search(r'\.(pdf|jpg|png|docx?)$',h,re.I): cand.append(h)
    for h in cand[:6]:
        rr=get(h)
        if rr is not None: pages[rr.url]=(BeautifulSoup(rr.text,'lxml'),rr.text)
    out={'Pages Checked':len(pages),'Yearbook Program':'Not Found','Yearbook Program/Contact Page':'','Current Yearbook Vendor':'Unknown','Vendor Evidence':'','Vendor Source URL':''}
    for url,(sp,raw) in pages.items():
        for v,pat in VENDORS:
            m=re.search(pat,raw,re.I)
            if m:
                ctx=re.search(r'href=["\']([^"\']*(?:'+pat+r')[^"\']*)',raw,re.I)
                out.update({'Current Yearbook Vendor':v,'Vendor Evidence':(ctx.group(1) if ctx else f'"{m.group(0)}" found in page text'),'Vendor Source URL':url}); break
        if out['Current Yearbook Vendor']!='Unknown': break
    ybp=[u for u,(sp,raw) in pages.items() if re.search(r'yearbook',u,re.I) or (YB_LINK.search(u) and re.search(r'yearbook',raw,re.I))]
    if ybp: out['Yearbook Program']='Confirmed (school site)'; out['Yearbook Program/Contact Page']=ybp[0]
    elif out['Current Yearbook Vendor']!='Unknown': out['Yearbook Program']='Confirmed (vendor link on site)'; out['Yearbook Program/Contact Page']=out['Vendor Source URL']
    elif yb: out['Yearbook Program']='Link present (not fetched)'; out['Yearbook Program/Contact Page']=yb[0]
    elif any(re.search(r'yearbook',raw,re.I) for _,(sp,raw) in pages.items()): out['Yearbook Program']='Mentioned on site'; out['Yearbook Program/Contact Page']=next(u for u,(sp,raw) in pages.items() if re.search(r'yearbook',raw,re.I))
    return out
def grab(t,label):
    m=re.search(label+r'\s*:?\s*(.+)',t,re.I); return m.group(1).strip() if m else ''
def clean_name(v):
    v=re.sub(r'\[\d+\]','',v).strip(' .*-–')
    if re.search(r'not found|unknown|not (publicly )?(listed|available|named|identified)|no (current|specific|public)|unable|could not|n/a|not specified',v,re.I): return ''
    m=NM.match(v); return m.group(1) if m else ''
def clean_email(v):
    m=EMAIL.search(v); return m.group(0) if m else ''
def llm_layer(r,site,web_search):
    q=(f'School: {r.SCH_NAME}, {r.LCITY}, {r.LSTATE} (district: {r.LEA_NAME}; website {site or "unknown"}). Using only the school/district website or other official public pages, answer on separate lines exactly: '
       'ADVISER: <current yearbook adviser/teacher full name or Not Found>\nADVISER_EMAIL: <school email or Not Found>\nPRINCIPAL: <current principal full name or Not Found>\nPRINCIPAL_EMAIL: <email or Not Found>\n'
       'VENDOR: <yearbook publisher: Jostens, Herff Jones, Walsworth, TreeRing, Entourage, Balfour, Lifetouch/Shutterfly, other, or Not Found>\nYEARBOOK_PAGE: <URL of the school yearbook/order page or Not Found>\nSOURCES: <URLs>. Do not guess; write Not Found when unsure.')
    res,err=web_search(q); t=str(res)
    urls=[u.rstrip('.,);') for u in URL.findall(t)]
    vraw=grab(t,'VENDOR'); vend=next((v for v in VEND_NAMES if re.search(re.escape(v),vraw,re.I)),'')
    if vend in ('Lifetouch','Shutterfly'): vend='Lifetouch/Shutterfly'
    yp=URL.search(grab(t,'YEARBOOK_PAGE'))
    return {'llm_adviser':clean_name(grab(t,'ADVISER')),'llm_adviser_email':clean_email(grab(t,'ADVISER_EMAIL')),'llm_principal':clean_name(grab(t,'PRINCIPAL')),'llm_principal_email':clean_email(grab(t,'PRINCIPAL_EMAIL')),'llm_vendor':vend,'llm_yearbook_page':(yp.group(0).rstrip('.,);') if yp else ''),'llm_sources':' | '.join(dict.fromkeys(urls))[:700],'llm_raw':t[:1500]}
def process(r,web_search):
    out={'NCESSCH':r.NCESSCH,'Website Verification Date':TODAY}
    site,src,status,resp=resolve_site(r,web_search)
    out.update({'School Website':site,'Website Source':src,'Website Status':status})
    if resp is not None:
        try: out.update(crawl(site,resp))
        except Exception as e: out['crawl_error']=str(e)[:120]
    try: out.update(llm_layer(r,site if status=='ok' else '',web_search))
    except Exception as e: out['llm_error']=str(e)[:120]
    return out
