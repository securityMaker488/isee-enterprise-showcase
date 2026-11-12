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

O validador falha FECHADO em tudo que nao consegue verificar: arquivo que
nao decodifica, historico inacessivel, repositorio clonado de forma rasa,
raiz que nao e a raiz do git. Nenhuma dessas condicoes pode virar
"aprovado".

    python scripts/validate-showcase.py [raiz-do-repositorio] [--tree-only]

``--tree-only`` valida apenas a arvore de trabalho. Use somente para a pasta
de fonte dentro do repositorio privado, onde o historico publicado e o do
repositorio publico e nao o deste.
"""
from __future__ import annotations

import argparse
import hashlib
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
    ".github/dependabot.yml",
    "scripts/validate-showcase.py",
}
ALLOWED_PREFIXES = ("docs/", "demo/", "assets/")

# Extensoes aceitas dentro dos caminhos permitidos. `.py` fica de fora: o
# unico script do repositorio publico e o proprio validador, tratado pelo
# caminho exato em ALLOWED_EXACT.
ALLOWED_SUFFIXES = {".md", ".json", ".png", ".svg", ".yml", ".yaml"}

# Extensoes cujo conteudo e texto e portanto inspecionado. As demais
# (`.png`) sao binarias: nao ha o que decodificar.
TEXT_SUFFIXES = {".md", ".json", ".svg", ".yml", ".yaml"}

MAX_FILE_BYTES = 2 * 1024 * 1024

SECRET_PATTERNS = (
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "chave privada"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "chave de API do Google"),
    (r"gh[pousr]_[A-Za-z0-9]{30,}", "token do GitHub"),
    (r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}", "chave de API"),
    (r"postgres(?:ql)?://[^:/\s\"']+:[^@/\s\"']+@", "URL de banco com senha"),
)

# Construcoes tipicas de codigo-fonte. A busca NAO e ancorada no inicio da
# linha e roda sobre o texto com espacos normalizados: codigo renormalizado
# (reformatado, compactado ou embutido em JSON/Markdown) ainda e
# reconhecido. Documentacao e dado sintetico nao contem estas formas.
SOURCE_PATTERNS = (
    # Python
    (r"\bdef\s+[A-Za-z_]\w*\s*\(", "definicao de funcao"),
    (r"\bclass\s+[A-Za-z_]\w*\s*[:(]", "definicao de classe"),
    (r"\bfrom\s+[\w.]+\s+import\b", "importacao"),
    (r"\bimport\s+[\w.]+\s*$", "importacao"),
    (r"\bself\.\w+\s*=", "atributo de instancia"),
    (r"\b__\w+__\s*\(", "metodo especial"),
    (r"\blambda\s+[\w,\s]*:", "funcao anonima"),
    # Java, C#, Kotlin, Scala
    (r"\b(?:public|private|protected)\s+static\s+[\w<>\[\],.\s]*\w+\s*\(",
     "metodo de classe"),
    (r"@Override\b", "anotacao de metodo"),
    (r"\bpackage\s+[\w.]+\s*;", "declaracao de pacote"),
    (r"\bnamespace\s+[\w.]+\s*\{", "namespace"),
    (r"\busing\s+System(?:\.[\w.]+)?\s*;", "using C#"),
    # C e C++
    (r"#include\s*[<\"]", "inclusao de cabecalho"),
    (r"\b(?:int|void|char|float|double|long|short|bool|size_t)\s+\w+\s*\([^;{]*\)\s*\{",
     "definicao de funcao"),
    (r"\bstd::", "namespace C++"),
    # Rust
    (r"\bfn\s+\w+\s*[(<]", "definicao de funcao"),
    (r"\buse\s+[\w:]+::", "use de modulo"),
    (r"\blet\s+mut\s+\w+", "declaracao Rust"),
    (r"\bimpl\s+\w+", "implementacao Rust"),
    # Go
    (r"\bfunc\s+\w+\s*\(", "definicao de funcao"),
    (r":=", "atribuicao Go"),
    # JavaScript e TypeScript
    (r"\bfunction\s+\w*\s*\(", "definicao de funcao"),
    (r"=>", "arrow function"),
    (r"\b(?:const|let|var)\s+\w+\s*=\s*require\(", "modulo CommonJS"),
    (r"\bmodule\.exports\b", "modulo CommonJS"),
    (r"\bexport\s+(?:default|const|function|class)\b", "modulo ES"),
    (r"\bconsole\.log\s*\(", "console JavaScript"),
    # PHP, shell e afins
    (r"<\?php", "codigo PHP"),
    (r"#!/usr/bin/env\s+\w+", "script executavel"),
)

LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def is_allowed_path(relative: str) -> bool:
    if relative in ALLOWED_EXACT:
        return True
    return relative.startswith(ALLOWED_PREFIXES)


def normalize_line(line: str) -> str:
    """Colapsa espacos: codigo renormalizado costuma ter espacos oddos."""
    return re.sub(r"\s+", " ", line).strip()


def inspect_content(relative: str, text: str, label: str) -> list[str]:
    """Regras de conteudo de um arquivo de texto.

    `relative` e o caminho real do arquivo (as excecoes de caminho usam
    esse valor); `label` e como o problema aparece no relatorio.
    """
    problems: list[str] = []
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, line):
                problems.append(f"{label}:{number}: {description}")
                break
    # Os arquivos de controle sao exemptos: o proprio validador e Python
    # por definicao. Nenhum outro caminho exato existe no repositorio
    # publico, e os tres Markdown sao texto de apresentacao.
    if relative not in ALLOWED_EXACT:
        for number, line in enumerate(lines, start=1):
            normalized = normalize_line(line)
            for pattern, description in SOURCE_PATTERNS:
                if re.search(pattern, normalized):
                    problems.append(
                        f"{label}:{number}: construcao de codigo-fonte ({description})"
                    )
                    break
    return problems


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_validator_binding(root: Path) -> list[str]:
    """O candidato nao pode trocar o proprio validador.

    O workflow executa a copia CONFIADAVEL (branch base). Se a copia
    candidata divergir, o pull request substituiu o proprio controle -- e a
    validacao passaria a ser feita pelo codigo de quem pediu a validacao.
    """
    trusted = Path(__file__).resolve()
    candidate = root / "scripts" / "validate-showcase.py"
    if not candidate.is_file():
        return [
            "scripts/validate-showcase.py: o validador nao esta presente na "
            "raiz validada"
        ]
    if candidate.resolve() == trusted:
        return []
    if file_digest(candidate) != file_digest(trusted):
        return [
            "scripts/validate-showcase.py: o validador candidato diverge da "
            "copia confiavel (SHA-256 diferente); um pull request nao pode "
            "substituir o proprio controle"
        ]
    return []


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
        suffix = path.suffix.lower()
        if relative not in ALLOWED_EXACT and suffix not in ALLOWED_SUFFIXES:
            problems.append(f"{relative}: extensao nao permitida ({suffix})")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            problems.append(f"{relative}: arquivo acima do limite de 2 MB")
            continue

        text = None
        if suffix in TEXT_SUFFIXES or relative in ALLOWED_EXACT:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Falha fechada: um conteudo que nao decodifica nao pode
                # ser declarado limpo.
                problems.append(f"{relative}: conteudo nao decodificavel em UTF-8")
                continue
            except OSError as error:
                problems.append(f"{relative}: falha ao ler o arquivo ({error})")
                continue
            problems.extend(inspect_content(relative, text, relative))

        if text is not None and suffix == ".md":
            for target in LINK_PATTERN.findall(text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                cleaned = target.split("#", 1)[0]
                if cleaned and not (path.parent / cleaned).exists():
                    problems.append(f"{relative}: link quebrado -> {target}")
    return problems


def inspect_history(root: Path, *, required: bool) -> list[str]:
    """Aplica as mesmas regras a todo blob ja publicado no historico.

    O historico so e verificado quando a raiz validada e a propria raiz do
    repositorio git: validando a pasta de fonte dentro do repositorio
    privado, o historico relevante seria o do codigo proprietario, e nao o
    do showcase.

    Quando o historico nao pode ser verificado, isso e um problema -- nao
    uma aprovacao silenciosa.
    """
    problems: list[str] = []

    def unverifiable(reason: str) -> list[str]:
        if required:
            return [f"historico: {reason}"]
        return []

    try:
        toplevel = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, check=True, text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        return unverifiable(f"nao foi possivel verificar o historico ({error})")

    try:
        if Path(toplevel).resolve() != root:
            return unverifiable(
                "a raiz validada nao e a raiz do repositorio git; o historico "
                "publicado nao pode ser verificado"
            )
    except OSError as error:
        return unverifiable(f"nao foi possivel verificar o historico ({error})")

    try:
        shallow = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
            capture_output=True, check=True, text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        return unverifiable(f"nao foi possivel verificar o historico ({error})")
    if shallow == "true":
        return unverifiable(
            "repositorio clonado de forma rasa; o historico completo nao pode "
            "ser verificado"
        )

    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--objects", "--all"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        return unverifiable(f"nao foi possivel verificar o historico ({error})")

    # `rev-list --objects` lista tambem as arvores de diretorio. O tipo do
    # objeto separa os dois: so os blobs correspondem a arquivos.
    try:
        checked = subprocess.run(
            ["git", "-C", str(root), "cat-file",
             "--batch-check=%(objecttype) %(objectname) %(objectsize) %(rest)"],
            input=listing, capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        return unverifiable(f"nao foi possivel verificar o historico ({error})")

    for line in checked.decode("utf-8", "replace").splitlines():
        kind, _, remainder = line.partition(" ")
        if kind != "blob":
            continue
        sha, _, rest = remainder.partition(" ")
        size_text, _, relative = rest.partition(" ")
        relative = relative.strip()
        if not relative or relative.startswith(".git/"):
            continue
        if not is_allowed_path(relative):
            problems.append(f"historico: {relative}: caminho nao permitido")
            continue
        suffix = Path(relative).suffix.lower()
        if relative not in ALLOWED_EXACT and suffix not in ALLOWED_SUFFIXES:
            problems.append(
                f"historico: {relative}: extensao nao permitida ({suffix})"
            )
            continue
        try:
            size = int(size_text)
        except ValueError:
            size = 0
        if size > MAX_FILE_BYTES:
            problems.append(
                f"historico: {relative}: arquivo acima do limite de 2 MB"
            )
            continue
        if suffix not in TEXT_SUFFIXES and relative not in ALLOWED_EXACT:
            continue
        try:
            content = subprocess.run(
                ["git", "-C", str(root), "cat-file", "blob", sha],
                capture_output=True, check=True,
            ).stdout
        except subprocess.CalledProcessError as error:
            problems.append(f"historico: {relative}: falha ao ler o blob ({error})")
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            problems.append(
                f"historico: {relative}: conteudo nao decodificavel em UTF-8"
            )
            continue
        problems.extend(inspect_content(relative, text, f"historico:{relative}"))
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Valida o repositorio publico de apresentacao."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1]),
        help="raiz do repositorio a validar",
    )
    parser.add_argument(
        "--tree-only",
        action="store_true",
        help=(
            "valida apenas a arvore de trabalho (use na pasta de fonte do "
            "repositorio privado, onde o historico publicado e o do "
            "repositorio publico)"
        ),
    )
    args = parser.parse_args(argv[1:])

    root = Path(args.root).resolve()
    problems = inspect_validator_binding(root)
    problems += inspect_tree(root)
    problems += inspect_history(root, required=not args.tree_only)

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
