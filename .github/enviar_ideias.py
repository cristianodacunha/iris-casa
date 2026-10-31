"""Manda para quem cuida da Iris as sugestões e lições ainda não enviadas (anotadas pela Iris, sem dados pessoais).

Só envia se a pessoa deixou (linha "enviar ideias: sim" em memoria/pessoa.md). O envio é assinado com a chave do
código de ativação, e a caixa só aceita cliente ativo. O que já foi enviado fica marcado em memoria/.ideias_enviadas.
"""
import base64
import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

CAIXA = "https://iris-ideias.cristianodacunha.workers.dev/ideia"
ENVIADAS = Path("memoria/.ideias_enviadas")

pessoa = Path("memoria/pessoa.md")
if not (pessoa.exists() and re.search(r"^enviar ideias:\s*sim\b", pessoa.read_text(encoding="utf-8"), re.M | re.I)):
    print("A pessoa não autorizou mandar ideias: nada enviado.")
    raise SystemExit(0)
ativacao = Path(".iris/ativacao")
m = re.search(r"IRIS-([0-9a-f]{16})-([A-Za-z0-9_-]{43})", ativacao.read_text(encoding="utf-8") if ativacao.exists() else "")
if not m:
    print("Sem código de ativação: nada enviado.")
    raise SystemExit(0)
ident, chave = m.group(1), base64.urlsafe_b64decode(m.group(2) + "=")

ja = set(ENVIADAS.read_text(encoding="utf-8").split()) if ENVIADAS.exists() else set()
itens, marcas = [], []
for tipo, nome in (("sugestao", "sugestoes.md"), ("licao", "licoes.md")):
    arq = Path("memoria") / nome
    if not arq.exists():
        continue
    for bloco in re.split(r"\n(?=## )", arq.read_text(encoding="utf-8")):
        if not bloco.startswith("## "):
            continue
        titulo, _, texto = bloco[3:].partition("\n")
        titulo = re.sub(r" \(\d{2}/\d{2}/\d{4}\)\s*$", "", titulo.strip())
        marca = hashlib.sha256(f"{tipo}|{titulo}|{texto.strip()}".encode()).hexdigest()[:20]
        if marca not in ja and texto.strip():
            itens.append({"tipo": tipo, "titulo": titulo[:200], "texto": texto.strip()[:2000]})
            marcas.append(marca)
for arq in sorted(Path("memoria/receitas").glob("*.md")):
    texto = arq.read_text(encoding="utf-8")[:9000]
    marca = hashlib.sha256(f"habilidade|{arq.name}|{texto}".encode()).hexdigest()[:20]
    if marca not in ja and texto.strip():
        titulo = texto.splitlines()[0].lstrip("# ").strip() or arq.stem
        itens.append({"tipo": "habilidade", "titulo": titulo[:200], "texto": texto})
        marcas.append(marca)

# Segunda barreira (a primeira é a ferramenta da Iris): nada com dado pessoal, segredo, endereço externo, comando
# de internet ou instrução de ataque sai daqui. O que for barrado fica marcado para não tentar de novo.
SUSPEITO = re.compile(
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b|\(?\b\d{2}\)?[\s-]?9?\d{4}[\s-]?\d{4}\b|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|"
    r"\b(?:\d[ -]?){13,19}\b|IRIS-[0-9a-f]{16}|\b(?:gh[pousr]_|github_pat_|sk-|xox[abp]-|AKIA)[A-Za-z0-9_-]{8,}|"
    r"[A-Za-z0-9+/_-]{48,}|https?://(?!(?:www\.)?github\.com/|raw\.githubusercontent\.com/)[^\s)]+|"
    r"\b(?:curl|wget|nc|ncat|scp|sftp|ftp)\b|requests\.(?:get|post|put)|urllib\.request|http\.client|socket\.|"
    r"smtplib|webhook|ignor\w*\s+(?:as\s+|todas\s+as\s+|the\s+|all\s+)?(?:instru\w+|regras|previous|prior|above)|"
    r"disregard|system\s*prompt|you\s+are\s+now|novas\s+instru\w+|\.nucleo|jailbreak", re.I)
barradas = [m for item, m in zip(itens, marcas) if SUSPEITO.search(item["titulo"] + "\n" + item["texto"])]
if barradas:
    print(f"Barradas pela varredura (não saem): {len(barradas)}")
    with open(ENVIADAS, "a", encoding="utf-8") as f:
        f.write("\n".join(barradas) + "\n")
itens, marcas = [i for i, m in zip(itens, marcas) if m not in barradas], [m for m in marcas if m not in barradas]
if not itens:
    print("Nenhuma ideia nova.")
    raise SystemExit(0)

itens, marcas = itens[:10], marcas[:10]   # receitas são maiores: até 10 por envio (o resto vai no próximo)
ts = int(time.time())
itens_json = json.dumps(itens, ensure_ascii=False)
assinatura = hmac.new(chave, f"{ident}.{ts}.{itens_json}".encode(), hashlib.sha256).hexdigest()
corpo = json.dumps({"id": ident, "ts": ts, "itens_json": itens_json, "assinatura": assinatura}).encode()
req = urllib.request.Request(CAIXA, data=corpo, method="POST",
                             headers={"content-type": "application/json", "user-agent": "iris-casa"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print("Enviado:", r.read().decode())
except urllib.error.HTTPError as e:
    print("A caixa recusou:", e.code, e.read().decode()[:200])
    raise SystemExit(0)
with open(ENVIADAS, "a", encoding="utf-8") as f:
    f.write("\n".join(marcas) + "\n")
