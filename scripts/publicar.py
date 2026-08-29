#!/usr/bin/env python3
"""publicar.py — promove rascunho -> publicado (robots index, tira banner, add sitemap).
Lê o domínio de site_config.json. Uso: python3 scripts/publicar.py <slug> [<slug2> ...]"""
import os, re, sys, json, datetime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOM=json.load(open(os.path.join(ROOT,"scripts","site_config.json"),encoding="utf-8"))["site"]["dominio"]
def publicar(slug):
    f=os.path.join(ROOT,"blog",slug,"index.html")
    if not os.path.exists(f): print(f"  ✗ não encontrado: {slug}"); return
    h=open(f,encoding="utf-8").read()
    h=re.sub(r'(<meta name="robots" content=")[^"]*(">)',r'\g<1>index, follow\g<2>',h,count=1)
    h=re.sub(r'\n?<div style="background:#FFF4CE;.*?</div>','',h,count=1,flags=re.S)
    open(f,"w",encoding="utf-8").write(h)
    sm=os.path.join(ROOT,"sitemap.xml"); s=open(sm,encoding="utf-8").read()
    loc=f"https://{DOM}/blog/{slug}/"
    if loc not in s:
        d=datetime.date.today().isoformat()
        s=s.replace("</urlset>",f'  <url><loc>{loc}</loc><lastmod>{d}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>\n</urlset>',1)
        open(sm,"w",encoding="utf-8").write(s)
    print(f"  ✓ publicado: /blog/{slug}/")
if __name__=="__main__":
    for s in sys.argv[1:]: publicar(s.strip().strip("/").replace("blog/",""))
