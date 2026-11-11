# Segurança e privacidade

## Controles de segurança

| Área | Controle |
|---|---|
| Autenticação | JWT com expiração, identificador único de token (`jti`) e revogação no logout. |
| Autorização | RBAC verificado no backend (Admin, Director, Secretary e perfis operacionais). |
| Multi-tenant | Escopo de organização aplicado no servidor; proteção contra IDOR/BOLA. |
| Credenciais de câmera | Senhas RTSP/ONVIF fora do modelo SQL, em gerenciador de segredos local. |
| Comunicação entre processos | Serviços nativos escutam apenas em loopback; o token de IPC é provisionado por instalação e exigido nas operações de controle. |
| Identidade da instalação | Chave de assinatura e credencial inicial geradas por instalação (CSPRNG) e persistidas no arquivo de ambiente da instalação — cada instalação é autossuficiente. |
| Instalação | Sem senhas padrão fixas; credencial inicial aleatória e arquivos sensíveis com ACL restrita ao usuário, ao SYSTEM e aos Administradores. |
| Logs | Sem segredos ou tokens em logs e argumentos de linha de comando. |
| Supply chain | Dependências fixadas e auditadas; artefatos nativos compilados a partir do código-fonte. |
| Repositório | Segredos, embeddings, fotos e bancos de dados de runtime nunca são versionados. |

## LGPD

- **Biometria opcional**: o reconhecimento facial não é obrigatório no cadastro de pessoas.
- **Minimização**: frames de vídeo são descartáveis; somente eventos confirmados são persistidos.
- **Retenção configurável** por organização e por câmera *(limpeza automática em desenvolvimento)*.
- **Finalidade**: dados biométricos usados apenas para a finalidade autorizada.
- **Embeddings** tratados como dado pessoal sensível, armazenados localmente e excluídos com o titular.
- **Auditoria** de correções manuais e ações administrativas.

## Crianças e adolescentes

Em ambientes escolares:

- Biometria somente com base legal adequada e autorização dos responsáveis.
- **Alternativa não biométrica garantida** para presença, alimentação e demais serviços essenciais.
- Relatórios de planejamento de alimentação são **agregados**, sem identificação individual.
- Falha ou indisponibilidade do reconhecimento nunca bloqueia o atendimento do estudante.

## Divulgação responsável

Veja [../SECURITY.md](../SECURITY.md).
