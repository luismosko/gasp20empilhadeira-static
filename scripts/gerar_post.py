#!/usr/bin/env python3
"""
gerar_post.py | v2.1.0 (KIT PORTÁVEL — listagem no layout do site)
Gerador de posts de blog, config-driven, para qualquer site estático (Cloudflare Pages).
NÃO tem nada hardcoded do negócio — tudo vem de scripts/site_config.json.

Cole este arquivo + enviar_email.py + publicar.py + o workflow em qualquer repo de site,
preencha o site_config.json, e funciona igual ao moskogas.

DEFAULT-DENY / SEGURANÇA:
  - Nasce RASCUNHO (noindex) a menos que PUBLICAR=1.
  - Preço (quando o site usa) nunca é inventado: IZGLP -> fallback config -> senão omite.
  - Guard-rail de anti-temas configurável (allowlist de intenção comercial-local).
  - CTA, persona, money-pages e temas: 100% do config.

Uso:
    ANTHROPIC_API_KEY=... python3 scripts/gerar_post.py           # rascunho
    ANTHROPIC_API_KEY=... PUBLICAR=1 python3 scripts/gerar_post.py # publica
    python3 scripts/gerar_post.py --dry-run                        # sem API (amostra)
"""
import os, re, sys, json, datetime, html as _html
import urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5").strip()
PUBLICAR = os.environ.get("PUBLICAR", "").strip() == "1"
IZGLP    = os.environ.get("IZGLP_PRECO_URL", "").strip()

MESES = ["janeiro","fevereiro","março","abril","maio","junho",
         "julho","agosto","setembro","outubro","novembro","dezembro"]


def load(name):
    return json.load(open(os.path.join(SCRIPTS, name), encoding="utf-8"))


# ─────────────────────────── helpers de listagem/sitemap (genéricos) ──────────
def regenerar_listagem(cfg):
    """Reconstrói os cards entre <!-- AUTO-INICIO --> e <!-- AUTO-FIM --> em blog/index.html.
    DEFAULT-DENY: rascunho (noindex) fica fora. Posts curados à mão (já listados
    fora do bloco AUTO) são preservados e nunca duplicados."""
    idx = os.path.join(ROOT, "blog", "index.html")
    if not os.path.exists(idx):
        return
    h = open(idx, encoding="utf-8").read()
    if "<!-- AUTO-INICIO -->" not in h:
        return
    fora = re.sub(r"<!-- AUTO-INICIO -->.*?<!-- AUTO-FIM -->", "", h, flags=re.S)
    try:
        cats = {t["slug"]: t.get("categoria", "geral") for t in load("fila_temas.json")}
    except Exception:
        cats = {}
    LABEL = {"economia": "Economia", "manutencao": "Manutenção", "operacao": "Operação",
             "seguranca": "Segurança", "empresas": "Empresas", "comparativos": "Comparativos",
             "geral": "GLP"}
    EMOJI = {"economia": "\U0001F4B0", "manutencao": "\U0001F527", "operacao": "\U0001F69C",
             "seguranca": "\U0001F9BA", "empresas": "\U0001F3ED", "comparativos": "\u2696\uFE0F",
             "geral": "\U0001F535"}
    cards = []
    for slug in sorted(os.listdir(os.path.join(ROOT, "blog"))):
        d = os.path.join(ROOT, "blog", slug)
        f = os.path.join(d, "index.html")
        if not os.path.isdir(d) or not os.path.exists(f):
            continue
        if f'/blog/{slug}/' in fora:          # já listado à mão: não duplica
            continue
        ph = open(f, encoding="utf-8").read()
        if 'content="noindex' in ph:          # rascunho não entra na listagem
            continue
        t = re.search(r"<title>(.*?)</title>", ph, re.S)
        title = (t.group(1).split("|")[0].strip() if t else slug)
        dm = re.search(r'"dateModified":\s*"([\d-]+)"', ph)
        date = dm.group(1) if dm else ""
        de = re.search(r'<meta name="description" content="(.*?)"', ph, re.S)
        desc = (de.group(1).strip() if de else "")[:150]
        cat = cats.get(slug, "geral")
        cards.append((date, f'      <a href="/blog/{slug}/" class="post-card">\n'
                            f'        <div class="thumb">{EMOJI.get(cat, EMOJI["geral"])}</div>\n'
                            f'        <div class="content">\n'
                            f'          <span class="tag">{LABEL.get(cat, "GLP")}</span>\n'
                            f'          <h3>{_html.escape(title)}</h3>\n'
                            f'          <p>{_html.escape(desc)}</p>\n'
                            f'          <span class="read-more">Ler artigo \u2192</span>\n'
                            f'        </div>\n      </a>'))
    cards.sort(reverse=True)
    bloco = "\n".join(c for _, c in cards)
    h = re.sub(r"<!-- AUTO-INICIO -->.*?<!-- AUTO-FIM -->",
               f"<!-- AUTO-INICIO -->\n{bloco}\n      <!-- AUTO-FIM -->", h, flags=re.S)
    open(idx, "w", encoding="utf-8").write(h)
    print(f"  listagem: {len(cards)} posts automáticos")


def add_sitemap(cfg, slug):
    sm = os.path.join(ROOT, "sitemap.xml")
    if not os.path.exists(sm):
        return
    s = open(sm, encoding="utf-8").read()
    loc = f'https://{cfg["site"]["dominio"]}/blog/{slug}/'
    if loc in s:
        return
    hoje = datetime.date.today().isoformat()
    s = s.replace("</urlset>",
        f'  <url><loc>{loc}</loc><lastmod>{hoje}</lastmod>'
        f'<changefreq>monthly</changefreq><priority>0.7</priority></url>\n</urlset>', 1)
    open(sm, "w", encoding="utf-8").write(s)


# ─────────────────────────── preço (opcional por site) ───────────────────────
def get_price(cfg):
    pc = cfg.get("preco", {})
    if not pc.get("ativo"):
        return None
    if IZGLP:
        try:
            with urllib.request.urlopen(IZGLP, timeout=20) as r:
                d = json.loads(r.read().decode())
            return {k: str(d[k]) for k in pc["fallback"].keys()}
        except Exception as e:
            print(f"  ! IZGLP off ({e}); fallback", file=sys.stderr)
    return dict(pc["fallback"])


# ─────────────────────────── seleção de tema + guard-rail ─────────────────────
def proximo_tema(cfg):
    anti = [re.compile(p, re.I) for p in cfg.get("anti_temas", [])]
    for t in load("fila_temas.json"):
        alvo = (t["tema"] + " " + t["slug"]).lower()
        if any(p.search(alvo) for p in anti):
            print(f"  ⨯ guard-rail barrou: {t['slug']}", file=sys.stderr); continue
        if not os.path.isdir(os.path.join(ROOT, "blog", t["slug"])):
            return t
    return None


def build_system(cfg, price):
    s = cfg["site"]
    persona = cfg["persona"].format(**s)
    regras = f"""
Regras OBRIGATÓRIAS:
- Foco em quem VAI COMPRAR/CONTRATAR em {s['cidade']}. Nada fora da intenção comercial-local.
- 1500 a 2000 palavras. Subtítulos <h2>/<h3>, parágrafos curtos. Sem inventar dados.
- OBRIGATÓRIO 1 elemento concreto e escaneável: tabela HTML (<table>) OU checklist OU lista numerada.
- Números sempre comprometidos (dê a faixa concreta, nunca só "varia").
- FAQ com no mínimo 7 perguntas reais + respostas objetivas.
- NÃO inclua <h1>, NÃO inclua a FAQ, NÃO inclua CTA no corpo_html (são injetados depois)."""
    if price:
        regras += f"\n- Se citar preço, use EXATAMENTE: {json.dumps(price, ensure_ascii=False)}."
    fmt = ('Responda SOMENTE com JSON válido (sem markdown): '
           '{"title":"...","meta_description":"...(máx 155, com a cidade)","corpo_html":"<p>...</p>...",'
           '"faq":[{"q":"...","a":"..."}, ...7+...]}')
    return persona + "\n" + regras + "\n" + fmt


def chamar_claude(cfg, tema, price):
    body = json.dumps({
        "model": MODEL, "max_tokens": 8000, "system": build_system(cfg, price),
        "messages": [{"role": "user", "content":
            f"TEMA: {tema['tema']}\nCATEGORIA: {tema['categoria']}\n"
            f"CIDADE: {cfg['site']['cidade']}\nGere o artigo."}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode())
    txt = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()
    txt = re.sub(r"^```(json)?|```$", "", txt, flags=re.M).strip()
    if "{" in txt and "}" in txt:
        txt = txt[txt.index("{"):txt.rindex("}") + 1]
    return json.loads(txt)


# ─────────────────────────── render ──────────────────────────────────────────
def faq_html(faq):
    itens = "\n".join(
        f'      <div class="faq-item"><button class="faq-btn">{_html.escape(f["q"])}</button>'
        f'<div class="faq-content"><p>{f["a"]}</p></div></div>' for f in faq)
    return f'    <h2>Perguntas frequentes</h2>\n    <div class="faq-list">\n{itens}\n    </div>'


def render(cfg, art, slug, cat, price, tpl):
    s = cfg["site"]
    dom = s["dominio"]
    title = art["title"].strip()
    money_url, money_ancora = cfg["money_pages"].get(cat, list(cfg["money_pages"].values())[0])

    link = (f'<p>Se você já quer resolver agora, veja nossa página de '
            f'<a href="{money_url}">{money_ancora}</a>.</p>')

    c = cfg["cta"]
    preco_linha = ""
    if price:
        preco_linha = f'<p style="color:#cfe0ff;margin-bottom:16px">{c["linha_preco"].format(**price)}</p>'
    wa = f'https://wa.me/{s["whatsapp"]}?text=' + urllib.parse.quote(c["wa_msg"])
    cta = (f'<div style="background:{c.get("bg","linear-gradient(130deg,#001A4D,#0055CC)")};border-radius:14px;'
           f'padding:28px;text-align:center;margin:32px 0">'
           f'<p style="color:#fff;font-size:1.1rem;font-weight:700;margin-bottom:6px">{c["titulo"]}</p>'
           f'{preco_linha}'
           f'<a href="{wa}" target="_blank" rel="noopener" style="display:inline-block;background:#25D366;'
           f'color:#fff;font-weight:700;padding:14px 28px;border-radius:50px">{c["botao"]}</a></div>')

    hoje = datetime.date.today()
    data_pt = f"{hoje.day} de {MESES[hoje.month-1]} de {hoje.year}"
    iso = hoje.isoformat()
    words = len(re.sub(r"<[^>]+>", " ", art["corpo_html"]).split())
    readmin = max(2, round(words / 200))
    crumb = title[:42]

    _cal, _clk = ("", "") if s.get("sem_emoji") else ("📅 ", "⏱️ ")
    article = (f'<article>\n  <div class="container">\n'
               f'    <nav class="crumbs"><a href="/">Início</a> › <a href="/blog/">Blog</a> › {crumb}</nav>\n'
               f'    <h1>{_html.escape(title)}</h1>\n'
               f'    <div class="meta"><span>{_cal}{data_pt}</span> · <span>{_clk}{readmin} min de leitura</span></div>\n'
               f'{art["corpo_html"]}\n    {link}\n{faq_html(art["faq"])}\n    {cta}\n  </div>\n</article>')

    graph = [
        {"@type": "Article", "headline": title, "description": art["meta_description"],
         "datePublished": iso, "dateModified": iso,
         "author": {"@type": "Organization", "name": s["nome"]},
         "publisher": {"@type": "Organization", "name": s["nome"]},
         "mainEntityOfPage": f"https://{dom}/blog/{slug}/"},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Início", "item": f"https://{dom}/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"https://{dom}/blog/"},
            {"@type": "ListItem", "position": 3, "name": crumb}]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", f["a"])}}
            for f in art["faq"]]}]
    schema = ('<script type="application/ld+json">\n'
              + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
              + "\n</script>")

    robots = "index, follow" if PUBLICAR else "noindex, nofollow"
    _rasc = "Rascunho" if s.get("sem_emoji") else "📝 Rascunho"
    banner = "" if PUBLICAR else ('<div style="background:#FFF4CE;border-bottom:1px solid #E6D68A;'
        f'padding:8px;text-align:center;font-size:13px;color:#7a5c00">{_rasc} — rode publicar.py para indexar.</div>')

    return (tpl
        .replace("{{DOMINIO}}", dom).replace("{{SITE_NOME}}", s["nome"])
        .replace("{{SLUG}}", slug).replace("{{TITLE}}", _html.escape(title))
        .replace("{{META_DESC}}", art["meta_description"].replace('"', "'"))
        .replace("{{ROBOTS}}", robots).replace("{{DATE}}", iso)
        .replace("{{CRUMB}}", crumb).replace("{{BANNER}}", banner)
        .replace("{{ARTICLE}}", article).replace("{{SCHEMA}}", schema))


def main():
    cfg = load("site_config.json")
    price = get_price(cfg)
    print(f"site: {cfg['site']['dominio']} | preço: {price or 'n/a'}")
    tema = proximo_tema(cfg)
    if not tema:
        print("fila vazia."); return
    print(f"tema: {tema['slug']} [{tema['categoria']}]")

    if "--dry-run" in sys.argv:
        art = load("amostra_dry_run.json")
    else:
        if not API_KEY:
            print("ERRO: defina ANTHROPIC_API_KEY (ou --dry-run).", file=sys.stderr); sys.exit(1)
        art = chamar_claude(cfg, tema, price)

    tpl = open(os.path.join(SCRIPTS, "template-post.html"), encoding="utf-8").read()
    slug = tema["slug"]
    out = render(cfg, art, slug, tema["categoria"], price, tpl)
    d = os.path.join(ROOT, "blog", slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(out)
    if PUBLICAR:
        add_sitemap(cfg, slug)
    regenerar_listagem(cfg)
    print(f"✓ /blog/{slug}/ {'PUBLICADO' if PUBLICAR else 'RASCUNHO (noindex)'}")

    gho = os.environ.get("GITHUB_OUTPUT")
    if gho and PUBLICAR:
        with open(gho, "a", encoding="utf-8") as g:
            g.write(f"slug={slug}\ntitle={art['title'].strip()}\n"
                    f"url=https://{cfg['site']['dominio']}/blog/{slug}/\npublished=1\n")


if __name__ == "__main__":
    main()
