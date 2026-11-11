#!/usr/bin/env python3
"""Validador do repositorio publico de apresentacao (showcase).

Este repositorio nao pode conter codigo-fonte proprietario, dados de
pessoas nem segredos. A validacao roda a cada push e falha se algo
proibido entrar.

O controle e por CAMINHO (default-deny), nao por extensao: uma lista de
extensoes permitidas aceitaria codigo-fonte renormalizado como ``.md``,
enquanto um caminho permitido so aceita material de apresentacao.

A varredura cobre tambem o HISTORICO: um arquivo removido no commit
seguinte continua publicado no repositorio.

    python scripts/validate-showcase.py [raiz-do-repositorio]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Caminhos permitidos, por prefixo. Tudo fora desta lista e recusado.
ALLOWED_EXACT = {
    "README.md",
    "LICENSE.md",
    "SECURITY.md",
    ".github/workflows/showcase.yml",
    "scripts/validate-showcase.py",
}
ALLOWED_PREFIXES = ("docs/", "demo/", "assets/")

# Extensoes aceitas dentro dos caminhos permitidos. `.py` fica de fora: o
# unico script do repositorio publico e o proprio validador, tratado pelo
# caminho exato em ALLOWED_EXACT.
ALLOWED_SUFFIXES = {".md", ".json", ".png", ".svg", ".yml", ".yaml"}

MAX_FILE_BYTES = 2 * 1024 * 1024

SECRET_PATTERNS = (
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "chave privada"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "chave de API do Google"),
    (r"gh[pousr]_[A-Za-z0-9]{30,}", "token do GitHub"),
    (r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}", "chave de API"),
    (r"postgres(?:ql)?://[^:/\s\"']+:[^@/\s\"']+@", "URL de banco com senha"),
)

# Construcoes tipicas de codigo-fonte. Documentacao e dado sintetico nao
# contem estas formas; codigo renormalizado em .md/.json contem.
SOURCE_PATTERNS = (
    (r"^\s*def\s+\w+\s*\(", "definicao de funcao"),
    (r"^\s*class\s+\w+[\(:]", "definicao de classe"),
    (r"^\s*import\s+[\w.]+", "importacao"),
    (r"^\s*from\s+[\w.]+\s+import\b", "importacao"),
    (r"^\s*(?:public|private|protected)\s+static\s+\w+", "metodo de classe"),
    (r"^\s*#include\s*[<\"]", "inclusao de cabecalho"),
    (r"^\s*func\s+\w+\s*\(", "funcao"),
    (r"^\s*function\s+\w+\s*\(", "funcao"),
)

LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def is_allowed_path(relative: str) -> bool:
    if relative in ALLOWED_EXACT:
        return True
    return relative.startswith(ALLOWED_PREFIXES)


def inspect_text(relative: str, text: str) -> list[str]:
    """Regras de conteudo aplicaveis a qualquer arquivo de texto."""
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, line):
                problems.append(f"{relative}:{number}: {label}")
                break
    if relative not in ALLOWED_EXACT and relative.endswith((".md", ".json", ".yml", ".yaml")):
        for number, line in enumerate(text.splitlines(), start=1):
            for pattern, label in SOURCE_PATTERNS:
                if re.search(pattern, line):
                    problems.append(
                        f"{relative}:{number}: construcao de codigo-fonte ({label})"
                    )
                    break
    return problems


def inspect_tree(root: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/"):
            continue
        if not is_allowed_path(relative):
            problems.append(f"{relative}: caminho nao permitido no repositorio publico")
            continue
        if relative not in ALLOWED_EXACT and path.suffix.lower() not in ALLOWED_SUFFIXES:
            problems.append(f"{relative}: extensao nao permitida ({path.suffix.lower()})")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            problems.append(f"{relative}: arquivo acima do limite de 2 MB")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        problems.extend(inspect_text(relative, text))
        if path.suffix.lower() == ".md":
            for target in LINK_PATTERN.findall(text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                cleaned = target.split("#", 1)[0]
                if cleaned and not (path.parent / cleaned).exists():
                    problems.append(f"{relative}: link quebrado -> {target}")
    return problems


def inspect_history(root: Path) -> list[str]:
    """Aplica as mesmas regras a todo blob ja publicado no historico.

    So e executado quando a raiz validada e a propria raiz do repositorio
    git: validando a pasta de fonte dentro do repositorio privado, o
    historico relevante seria o do codigo proprietario, e nao o do showcase.
    """
    problems: list[str] = []
    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, check=True, text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return problems

    try:
        if Path(toplevel).resolve() != root:
            return problems
    except OSError:
        return problems

    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--objects", "--all"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return problems

    # `rev-list --objects` lista tambem as arvores de diretorio. O tipo do
    # objeto separa os dois: so os blobs correspondem a arquivos.
    try:
        checked = subprocess.run(
            ["git", "-C", str(root), "cat-file",
             "--batch-check=%(objecttype) %(objectname) %(rest)"],
            input=listing, capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return problems

    for line in checked.decode("utf-8", "replace").splitlines():
        kind, _, remainder = line.partition(" ")
        if kind != "blob":
            continue
        sha, _, relative = remainder.partition(" ")
        relative = relative.strip()
        if not relative or relative.startswith(".git/"):
            continue
        if not is_allowed_path(relative):
            problems.append(f"historico: {relative}: caminho nao permitido")
            continue
        if not relative.endswith((".md", ".json", ".yml", ".yaml", ".py")):
            continue
        try:
            content = subprocess.run(
                ["git", "-C", str(root), "cat-file", "blob", sha],
                capture_output=True, check=True,
            ).stdout
        except subprocess.CalledProcessError:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        problems.extend(inspect_text(f"historico:{relative}", text))
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[1]
    problems = inspect_tree(root) + inspect_history(root)

    if problems:
        print("Repositorio publico invalido:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("Showcase valido: caminho permitido, sem codigo-fonte, sem segredos, "
          "links internos resolvem, historico limpo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
