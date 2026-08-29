#!/usr/bin/env python3
"""enviar_email.py — notifica (Resend) post publicado. Env: RESEND_API_KEY, MAIL_TO, POST_TITLE, POST_URL.
Sem chave -> pula. Falha -> non-fatal. Nunca quebra o pipeline."""
import os,json,sys,urllib.request
key=os.environ.get("RESEND_API_KEY","").strip(); to=os.environ.get("MAIL_TO","").strip()
title=os.environ.get("POST_TITLE","(sem título)").strip(); url=os.environ.get("POST_URL","").strip()
if not key or not to: print("email: sem chave — pulando."); sys.exit(0)
html=f"<p>Post novo publicado:</p><p><a href='{url}'>{title}</a></p><p>Quer mudar algo? Peça no chat.</p>"
body=json.dumps({"from":"Blog Bot <blog@moskogas.com.br>","to":to,"subject":f"✅ Post publicado: {title}","html":html}).encode()
req=urllib.request.Request("https://api.resend.com/emails",data=body,method="POST",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","User-Agent":"MoskoBlogBot/1.0 (+https://moskogas.com.br)"})
try:
    with urllib.request.urlopen(req,timeout=30) as r: print("email enviado:",r.status)
except Exception as e: print("email falhou (non-fatal):",e)
sys.exit(0)
