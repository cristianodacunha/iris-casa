"""Arquivo morto: tira da casa principal os documentos (fotos, PDFs, planilhas recebidas) com mais de 12 meses e os
guarda no ramo arquivo-morto, num commit que o download das conversas não traz (a ponta do ramo fica vazia).
JSON, fichas e anotações ficam na casa. Os links continuam funcionando: dados/arquivo_morto.jsonl guarda onde cada
arquivo está. Pedido antecipado: a Iris grava dados/.arquivar com uma data ("antes: AAAA-MM-DD").
Só mexe nos arquivos; quem faz o commit na casa é o passo seguinte da regra de junção.
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

LEVES = {".md", ".json", ".jsonl", ".csv", ".txt", ".ics"}   # anotações e dados: ficam na casa


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True).stdout.strip()


pedido = Path("dados/.arquivar")
limite = dt.date.today() - dt.timedelta(days=365)
if pedido.exists():
    m = re.search(r"\d{4}-\d{2}-\d{2}", pedido.read_text(encoding="utf-8"))
    if m:
        limite = min(dt.date.fromisoformat(m.group(0)), dt.date.today())
candidatos = []
for base in ("dados", "arquivos"):
    for arq in sorted(Path(base).rglob("*")) if Path(base).exists() else []:
        if not arq.is_file() or arq.suffix.lower() in LEVES or arq.name.startswith(".") or "json" in arq.parts[:2]:
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2}) ", arq.name)
        if m and dt.date.fromisoformat(m.group(1)) < limite:
            candidatos.append(arq.as_posix())
if not candidatos:
    if pedido.exists():
        git("rm", "-q", "--", str(pedido), check=False)
    print("Arquivo morto: nada para arquivar.")
    raise SystemExit(0)

tmp = tempfile.mkdtemp()
tem_ramo = bool(git("ls-remote", "--heads", "origin", "arquivo-morto", check=False))
if tem_ramo:
    git("fetch", "-q", "origin", "arquivo-morto")
    git("worktree", "add", "-q", "-B", "arquivo-morto", tmp, "FETCH_HEAD")
else:
    git("worktree", "add", "-q", "--detach", tmp)
    git("checkout", "-q", "--orphan", "arquivo-morto", cwd=tmp)
    git("rm", "-rf", "-q", ".", cwd=tmp, check=False)
for c in candidatos:
    destino = Path(tmp) / c
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(c, destino)
git("add", "-A", cwd=tmp)
git("commit", "-q", "-m", f"Arquivo morto: {len(candidatos)} arquivo(s) anteriores a {limite}", cwd=tmp)
sha = git("rev-parse", "HEAD", cwd=tmp)
git("rm", "-q", "-r", "--", *candidatos, cwd=tmp)
Path(tmp, "README.md").write_text("# Arquivo morto da Iris\n\nOs documentos antigos ficam nos commits anteriores deste "
                                  "ramo. A casa guarda onde está cada um em dados/arquivo_morto.jsonl.\n", encoding="utf-8")
git("add", "-A", cwd=tmp)
git("commit", "-q", "-m", f"Arquivo morto guardado em {sha[:12]} (ponta vazia: as conversas não baixam)", cwd=tmp)
git("push", "-q", "origin", "arquivo-morto", cwd=tmp)
git("worktree", "remove", "--force", tmp, check=False)

hoje = dt.date.today().isoformat()
with open("dados/arquivo_morto.jsonl", "a", encoding="utf-8") as f:
    for c in candidatos:
        f.write(json.dumps({"caminho": c, "sha": sha, "quando": hoje}, ensure_ascii=False) + "\n")
git("rm", "-q", "--", *candidatos)
if pedido.exists():
    git("rm", "-q", "--", str(pedido), check=False)
git("add", "dados/arquivo_morto.jsonl")
print(f"Arquivo morto: {len(candidatos)} arquivo(s) guardados em {sha[:12]}.")
