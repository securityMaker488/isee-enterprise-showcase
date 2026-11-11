# Engenharia e qualidade

## Ciclo de engenharia (V2.1)

O produto evolui em ciclos verificáveis: auditoria do código real → correção da causa raiz →
testes automatizados → documentação. Nenhuma funcionalidade é declarada concluída sem validação.

## Resultados medidos — novembro/2026

| Suíte | Comando (base privada) | Resultado |
|---|---|---|
| Backend | `pytest backend/tests` | 326 aprovados, 3 ignorados |
| Serviços nativos Rust | `cargo test --workspace` | 14 aprovados |
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
- Token do canal entre o backend e os serviços nativos provisionado por
  instalação e exigido nas operações de controle; prova de ponta a ponta com o
  binário nativo real (recusa sem token, aceita com o token correto).
- Instalador: o payload deixa de embutir embeddings, fotos, bancos de runtime,
  a suíte de testes e artefatos de build.

## O que não afirmamos

- Não divulgamos precisão biométrica sem protocolo de avaliação apropriado.
- Métricas de desempenho por número de câmeras dependem do hardware e serão publicadas apenas quando medidas.
- Distribuição Linux está em preparação e não é declarada pronta para produção.
