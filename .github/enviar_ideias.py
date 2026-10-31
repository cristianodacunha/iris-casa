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
if not itens:
    print("Nenhuma ideia nova.")
    raise SystemExit(0)

itens, marcas = itens[:30], marcas[:30]
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
