# Engenharia e qualidade

## Ciclo de engenharia (V2.1)

O produto evolui em ciclos verificáveis: auditoria do código real → correção da causa raiz →
testes automatizados → documentação. Nenhuma funcionalidade é declarada concluída sem validação.

## Resultados medidos — novembro/2026

| Suíte | Comando (base privada) | Resultado |
|---|---|---|
| Backend | `pytest backend/tests` | 385 aprovados, 3 ignorados |
| Serviços nativos Rust | `cargo test --workspace` | 19 aprovados |
| Desktop JavaFX | `mvn test` | 37 aprovados |

Os testes ignorados exigem PostgreSQL dedicado de testes ou ambiente Windows específico.

## Correções relevantes do ciclo atual

**Serviços nativos (Rust)**
- Supervisor: corrigido defeito que impedia o primeiro início dos processos filhos; coleta do processo
  após término (sem zumbis); encerramento gracioso antes de término forçado; identificação exata de PID.
- Camera Engine: porta padrão correta por esquema (HTTP 80, HTTPS 443, RTSP 554, RTSPS 322);
  timeouts de escrita; limite de conexões simultâneas; threads de câmeras desativadas encerram corretamente.
- Edge Agent: limite de tamanho de requisição; contagem de outbox por streaming (sem carregar o arquivo
  inteiro em memória); reescrita atômica do outbox; token de acesso fora dos argumentos do processo.

**Backend**
- Revogação de sessão (logout) e identificador único de token.
- Correção de IDOR entre organizações nas rotas da I.See AI.
- Publicação de eventos para a borda em fila assíncrona limitada (não bloqueia o EventBus).

**Ciclo de segurança da instalação**
- O arquivo de ambiente da instalação passou a ser o consumedor efetivo da
  configuração pelo backend: antes, a chave de assinatura era efêmera por
  processo e toda sessão morria a cada reinício.
- Credencial inicial de administrador gerada por instalação (CSPRNG), sem senha
  padrão fixa; rotação única de credenciais legadas e arquivo de credenciais com
  ACL restrita.
- Os segredos da instalação (chave de assinatura, token do canal IPC,
  credencial inicial) são gravados em arquivo com ACL restrita ao usuário, ao
  SYSTEM e aos Administradores — o arquivo é criado vazio, protegido e só
  então recebe o conteúdo.
- Token do canal entre o backend e os serviços nativos provisionado por
  instalação e exigido nas operações de controle; prova de ponta a ponta com o
  binário nativo real (recusa sem token, aceita com o token correto).
- Instalador: o payload deixa de embutir embeddings, fotos, bancos de runtime,
  a suíte de testes e artefatos de build.

**Ciclo de segurança do arquivo de ambiente**
- O arquivo de ambiente da instalação passou a ser lido pela **mesma gramática
  em todos os componentes** (o `python-dotenv` do backend): launcher, backend e
  supervisor nativo leem o mesmo valor efetivo.
- Antes, o launcher aproximava a leitura e o backend lia de outra forma: uma
  senha pública seguida de comentário ao final da linha passava pela
  validação e sobrevivia à rotação. Agora a rotação usa o valor efetivo.
- O token do canal IPC repassado aos serviços nativos é o mesmo que o backend
  valida — o supervisor não reinterpretava o arquivo por conta própria.
- O arquivo de ambiente da instalação é gravado sem BOM, para que a primeira
  chave seja legível por qualquer leitor.

**Ciclo de segurança do repositório público**
- O validador falha fechado: arquivo que não decodifica, histórico inacessível,
  clone raso ou raiz que não é a raiz do Git são recusados — nunca aprovados.
- O validador é vinculado à cópia confiável (SHA-256): um pull request não
  pode substituir o próprio controle.
- A detecção de código-fonte é agnóstica de linguagem e alcança código
  renormalizado em Markdown, JSON ou YAML.
- As ações do pipeline são fixadas no commit exato, e o dependabot é quem
  avança esses SHAs.

## O que não afirmamos

- Não divulgamos precisão biométrica sem protocolo de avaliação apropriado.
- Métricas de desempenho por número de câmeras dependem do hardware e serão publicadas apenas quando medidas.
- Distribuição Linux está em preparação e não é declarada pronta para produção.
