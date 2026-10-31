#!/usr/bin/env bash
# Busca o cérebro da Iris: baixa o pacote trancado desta casa, abre com a chave do código de ativação
# (guardado em .iris/ativacao) e coloca em .nucleo/, que nunca é guardado aqui. Sem acesso, apaga o que sobrou.
#   bash iniciar.sh                    -> NUCLEO_OK | NUCLEO_SEM_ATIVACAO | NUCLEO_SEM_ACESSO | NUCLEO_SEM_REDE
#   bash iniciar.sh ativar "IRIS-..."  -> guarda o código nesta casa e já busca o cérebro
cd "$(dirname "$0")" || exit 0
exec python3 - "$@" <<'PY'
import base64, hashlib, hmac, io, os, re, shutil, subprocess, sys, tarfile, time
import urllib.error, urllib.request
from pathlib import Path

ENTREGA = os.environ.get("IRIS_ENTREGA_URL", "https://raw.githubusercontent.com/cristianodacunha/iris-entrega/main")
ATIVACAO = Path(".iris/ativacao")
FORMATO = re.compile(r"IRIS-([0-9a-f]{16})-([A-Za-z0-9_-]{43})")


def fluxo(chave, nonce, tamanho):
    k = hashlib.sha256(b"enc" + chave).digest()
    return b"".join(hashlib.sha256(k + nonce + i.to_bytes(8, "big")).digest()
                    for i in range((tamanho + 31) // 32))[:tamanho]


def abrir(pacote, chave):
    if not pacote.startswith(b"IRIS1"):
        raise ValueError("pacote estranho")
    nonce, selo, cifra = pacote[5:21], pacote[21:53], pacote[53:]
    if not hmac.compare_digest(selo, hmac.new(hashlib.sha256(b"mac" + chave).digest(), nonce + cifra,
                                              hashlib.sha256).digest()):
        raise ValueError("chave não confere")
    return bytes(a ^ b for a, b in zip(cifra, fluxo(chave, nonce, len(cifra))))


def baixar(rel):
    url = f"{ENTREGA}/{rel}" + (f"?t={int(time.time())}" if ENTREGA.startswith("http") else "")
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def ativar(texto):
    m = FORMATO.search(texto or "")
    if not m:
        print("CODIGO_INVALIDO")
        return False
    ATIVACAO.parent.mkdir(exist_ok=True)
    ATIVACAO.write_text(m.group(0) + "\n", encoding="utf-8")
    git("add", str(ATIVACAO))
    git("-c", "user.name=Iris", "-c", "user.email=iris@users.noreply.github.com", "commit", "-q",
        "-m", "Iris: código de ativação")
    ramo = git("branch", "--show-current").stdout.strip()
    if ramo in ("", "main", "master"):
        ramo = f"iris/ativacao-{int(time.time())}"
        git("checkout", "-q", "-b", ramo)
    envio = git("push", "-q", "-u", "origin", ramo)
    print("ATIVADO" + ("" if envio.returncode == 0 else " (guardado aqui; para valer nas próximas conversas, Criar PR)"))
    return True


def buscar():
    if not ATIVACAO.exists():
        print("NUCLEO_SEM_ATIVACAO")
        return
    m = FORMATO.search(ATIVACAO.read_text(encoding="utf-8"))
    if not m:
        print("NUCLEO_SEM_ATIVACAO (o código guardado está incompleto)")
        return
    ident, chave = m.group(1), base64.urlsafe_b64decode(m.group(2) + "=")
    try:
        pacote = baixar(f"p/{ident}.iris")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            shutil.rmtree(".nucleo", ignore_errors=True)
            print("NUCLEO_SEM_ACESSO (sem pacote ativo para este código)")
        else:
            print(f"NUCLEO_SEM_REDE (HTTP {e.code})")
        return
    except Exception as e:  # noqa: BLE001 (qualquer falha de rede vira o mesmo aviso)
        if isinstance(getattr(e, "reason", None), FileNotFoundError):   # entrega local (testes): pacote apagado
            shutil.rmtree(".nucleo", ignore_errors=True)
            print("NUCLEO_SEM_ACESSO (sem pacote ativo para este código)")
        else:
            print(f"NUCLEO_SEM_REDE ({e})")
        return
    try:
        cerebro = abrir(pacote, chave)
    except ValueError as e:
        shutil.rmtree(".nucleo", ignore_errors=True)
        print(f"NUCLEO_SEM_ACESSO ({e})")
        return
    try:
        libs = baixar("libs.tar.gz")
    except Exception as e:  # noqa: BLE001
        print(f"NUCLEO_SEM_REDE (bibliotecas: {e})")
        return
    novo = Path(".nucleo.novo")
    shutil.rmtree(novo, ignore_errors=True)
    novo.mkdir()
    for blob in (cerebro, libs):
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            try:
                tar.extractall(novo, filter="data")
            except TypeError:
                tar.extractall(novo)
    shutil.rmtree(".nucleo", ignore_errors=True)
    novo.rename(".nucleo")
    versao = (Path(".nucleo/VERSAO").read_text(encoding="utf-8").strip() if Path(".nucleo/VERSAO").exists() else "?")
    print(f"NUCLEO_OK versão {versao}")


if len(sys.argv) > 1 and sys.argv[1] == "ativar":
    if ativar(" ".join(sys.argv[2:])):
        buscar()
else:
    buscar()
PY
