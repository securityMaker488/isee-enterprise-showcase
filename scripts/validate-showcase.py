#!/usr/bin/env python3
"""Validador do repositorio publico de apresentacao (showcase).

Este repositorio nao pode conter codigo-fonte proprietario, dados de
pessoas nem segredos. A validacao roda a cada push e falha se algo
proibido entrar.

    python scripts/validate-showcase.py [raiz-do-repositorio]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Extensoes permitidas: apresentacao, documentacao e dados sinteticos.
ALLOWED_SUFFIXES = {".md", ".json", ".png", ".svg", ".yml", ".yaml", ".py"}

# Extensoes que indicariam codigo-fonte ou artefato de build.
FORBIDDEN_SUFFIXES = {
    ".java", ".kt", ".rs", ".go", ".c", ".h", ".cpp", ".cs", ".js", ".jsx",
    ".ts", ".tsx", ".php", ".rb", ".swift", ".class", ".jar", ".exe", ".dll",
    ".pkl", ".npy", ".npz", ".onnx", ".db", ".sqlite", ".sqlite3", ".zip",
    ".tar", ".gz", ".7z",
}

SECRET_PATTERNS = (
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "chave privada"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "chave de API do Google"),
    (r"gh[pousr]_[A-Za-z0-9]{30,}", "token do GitHub"),
    (r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}", "chave de API"),
    (r"postgres(?:ql)?://[^:/\s\"']+:[^@/\s\"']+@", "URL de banco com senha"),
)

MAX_FILE_BYTES = 2 * 1024 * 1024
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parents[1]
    problems: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/") or relative == "scripts/validate-showcase.py":
            continue

        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            problems.append(f"{relative}: arquivo nao permitido no repositorio publico")
            continue
        if suffix not in ALLOWED_SUFFIXES:
            problems.append(f"{relative}: extensao nao permitida ({suffix})")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            problems.append(f"{relative}: arquivo acima do limite de 2 MB")
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for pattern, label in SECRET_PATTERNS:
            for number, line in enumerate(text.splitlines(), start=1):
                if re.search(pattern, line):
                    problems.append(f"{relative}:{number}: {label}")
                    break

        if suffix == ".md":
            for target in LINK_PATTERN.findall(text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                cleaned = target.split("#", 1)[0]
                if not cleaned:
                    continue
                if not (path.parent / cleaned).exists():
                    problems.append(f"{relative}: link quebrado -> {target}")

    if problems:
        print("Repositorio publico invalido:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("Showcase valido: sem codigo-fonte, sem segredos, links internos resolvem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
