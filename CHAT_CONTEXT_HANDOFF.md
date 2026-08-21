# Contexto do chat (handoff) — Tese LLM Broadcast Verification

Este ficheiro resume, em detalhe, o estado do trabalho e tudo o que foi feito nesta
sessão, para poder continuar numa conversa nova como se fosse a mesma.

## Quem / o quê
- Tese de mestrado (IST / Universidade de Lisboa). Aluna: Luana Lourenço Ferraz.
- Orientadores: Diogo (principal) e Miguel Correia.
- Objetivo: avaliar se LLMs conseguem verificar propriedades de correção de
  algoritmos distribuídos de broadcast (marcar cada propriedade como satisfeita ou violada).

## Preferências de escrita e estilo (IMPORTANTE seguir)
- Responder e escrever em português europeu quando a utilizadora escreve em português.
- Prosa com frases longas e explicativas, não listas curtas, nos documentos escritos.
- SEM travessões (—) no meio das frases. Sem setas (→) em documentos finais.
- Tabelas devem mostrar a verdade lado a lado (accuracy dos corretos E deteção dos com erro), não enganar.
- Títulos da apresentação: fonte normal, tamanho 15, negrito, SEM números, sem underline, sem subtítulos cinzentos, sem explicações a itálico.
- Dizer "Diogo" (não "Prof. Diogo"). Nunca "modelos de fronteira"; usar "modelos com maior potencial".
- Ao descrever os algoritmos novos, NÃO indicar o nome final que ficou nem as suas propriedades.
- Preservar sempre as edições manuais da utilizadora; NUNCA regenerar por cima sem confirmar.

## Modelos e mapeamentos
- iaedu-model-1 = GPT-5.5 (agente iaedu `cmor5objoex9gfp01vm7p95jh`, FUNCIONA).
- iaedu-model-2 = Claude Opus 4 (agente iaedu `cmoss7l0f658oko01vk2egfpg`, DESAPARECEU:
  a API responde "Agent not found". Não depende da aluna; é preciso ID novo do dashboard iaedu).
- llama-3.3-70b-groq = LLaMA-3.3-70B via Groq (aisuite; precisa de GROQ_API_KEY no ambiente).
- qwen2.5-coder-7b = Qwen local via Ollama (`ollama pull qwen2.5-coder:7b`).
- DeepSeek: abandonado (sempre "Insufficient Balance"; a aluna decidiu deixá-lo cair).

## Classificação do parser (update_excel.py)
- correct = todas as propriedades satisfeitas; wrong = alguma marcada não-satisfeita;
  incorrect_output = formato não reconhecido; error = sem resposta (rate-limit/timeout/API).
- Accuracy (algoritmos corretos) só conta se TODAS as propriedades forem satisfeitas.
- Deteção (variantes com erro _B) conta se PELO MENOS UMA propriedade for marcada violada.
- O parser procura a ÚLTIMA ocorrência de cada propriedade (fix já aplicado).
- Suporta ficheiros da iaedu (JSON-stream: usa a linha final `type: "message"`).

## O que foi feito NESTA sessão (por ordem)

### 1. Análise do lote do Diogo (4 ZIPs em `diogo/`)
- ZIPs: results_133.zip, results_200.zip, results_26.zip, results_76.zip.
- Extraídos para `diogo/_unzipped/` (reprodutível; excluído do arquivo de migração).
- 200 pastas de resultados, MAS ~195 eram só tentativas do DeepSeek falhadas.
- Usam o conjunto novo `algorithms_v3` + prompts reestruturados.
- Script de análise criado: `diogo/analyze_diogo.py` (importa update_excel).

### 2. Resultados válidos (727 testes; só 3 modelos)
- DeepSeek: 0 válidos (sem créditos). Claude: 0 válidos (agente 404).
- Contagem: só 14 pastas tinham resultado válido de um modelo que funciona.
- Por modelo:
  - GPT-5.5: 167 válidos; accuracy corretos 38% (41/107); deteção 100% (60/60).
  - LLaMA-70B: 280 válidos; accuracy 91% (164/180); deteção 80% (80/100). Muitos erros por rate-limit Groq.
  - Qwen-7B: 280 válidos; accuracy 77% (139/180); deteção 90% (90/100). Zero erros de API.
- NOVIDADE: Qwen (pequeno) detetou 90% dos erros (antes ~0%). Prompts + pseudocódigo unificado ajudaram.
- GPT-5.5 hipersensível: chumba corretos (38%) mas deteta todos os erros (100%).

### 3. Diagnóstico do Claude/iaedu
- O agent id do Claude está igual ao dos scripts antigos, MAS o agente foi removido do
  servidor iaedu. Confirmado em direto: model-1 responde, model-2 dá "Agent not found".
- Verificado que o Claude JÁ funcionou antes (results_9_miguel tinha respostas reais).

### 4. Tabelas por algoritmo, propriedade e modelo de falha
- Por algoritmo: GPT binário (100% em reliable-broadcast/fault-tolerant/general-omission,
  0% em best-effort/echo/bracha/imbs/rb-crash, os de relay/quórum). LLaMA falha imbs_B (25%).
- Causas dos 0% do GPT (com citações reais extraídas via `diogo/gpt_reasons.py`):
  - A: lê mal o fluxo type0/type1 no best-effort (acha que a entrega espera type1 nunca enviado).
    Possível efeito colateral da unificação dos nomes de mensagem.
  - B: vê ataque Bizantino mas não verifica que o quórum o impede (echo, bracha, imbs).
  - C: raciocina fora do modelo (N <= 2f, envios parciais) no rb-crash.
- Falsos positivos por propriedade (corretos): GPT alto em Validity 43%, Integrity 50%,
  Agreement 40%, Uniform Agreement 36%; No duplication 0%. LLaMA quase tudo 0%.
- Por modelo de falha (accuracy corretos): Crash GPT 40/LLaMA 80/Qwen 76; Omissão 92/100/65;
  Bizantino 0/100/75; Sem falhas 92/100/100. Deteção: Crash 100/92/93; Bizantino 100/62/85.

### 5. Sugestões do Diogo implementadas (conjunto `algorithms_v3`)
- Ignorar: Terminating Reliable Broadcast (x2), new-byzantine-rb, byzantine-rb (tinham falha).
- Adicionar: Bracha's Byzantine RB, Imbs & Raynal Byzantine RB, Majority-Ack Uniform RB (Cachin §3.4.3).
- Encurtar prompts (só mudou os templates, não o método de cada estratégia).
- Unificar pseudocódigo: 7 secções, estado comum (msg_sent, msg_received, delivered_value),
  tipos genéricos type0/type1/type2, subsecção "Assumptions". Antes eram até 13 secções com
  nome/referência no topo e variáveis específicas (sent_echo etc.) e labels SEND/ECHO/READY.
- 9 corretos + 5 variantes com erro (_B). Erros injetados:
  - best-effort_B: envia a todos exceto a si próprio.
  - reliable-broadcast_B: passo de relay removido (quebra Agreement).
  - echo-broadcast_B: regra f+1 READY removida (quebra Agreement).
  - imbs-byzantine-rb_B: limiar (n+f)/2 em vez de (n+f+1)/2.
  - uniform-reliable-broadcast_B: entrega com 1 ACK em vez de > n/2 (quebra Uniform Agreement).
- Fontes: best-effort/reliable/uniform = Cachin et al. (2011); general-omission = Hadzilacos & Toueg (1994);
  echo + bracha = Bracha (1987); imbs = Imbs & Raynal; rb-crash + fault-tolerant = Vaz et al. (IEEE Access).

### 6. Email ao Diogo (a aluna não pôde ir à reunião)
- Reunião remarcada para quinta 15h30; preciso de apresentação + artigo para esse dia.

### 7. Apresentação (Word) — `diogo/apresentacao_resultados.docx`
- Gerada por `diogo/make_presentation.py` (python-docx). IMPORTANTE: regenerar apaga edições
  manuais no docx. A utilizadora já perdeu edições uma vez por eu regenerar por cima.
- Estilo já ajustado às preferências dela (ver secção de estilo acima).
- Inclui: contexto, sugestões (prosa), template antigo vs novo (com excerto de código),
  testes, resultados por modelo, por algoritmo (com coluna de fonte e de tipo de erro),
  causas dos 0% do GPT, por propriedade, por modelo de falha, próximos passos.
- NÃO voltar a correr make_presentation.py sem confirmar com a utilizadora.
- Excel de apoio: `diogo/resumo_resultados.xlsx` (gerado por `diogo/make_summary_xlsx.py`).

### 8. Organização de pastas
- `results_data/` <- todas as pastas results_* + results (174 pastas, ~19k ficheiros, 49M).
- `archive/` <- zips soltos, pastas duplicadas " 2", e `archive/loose_version_files/` (v0_/v1_/v2_/v3_*.txt).
- Scripts atualizados para usar `RESULTS_ROOT = BASE_DIR / "results_data"`:
  update_excel.py, script-2.py, script-chat.py, script-miguel.py, script-fill-gaps.py,
  run_and_update.py, script.py. Todos compilam; update_excel descobre 160 conjuntos.

### 9. Runner único — `run_once.py` + `prompts/combined.txt`
- Corre GPT-5.5, LLaMA-70B e Qwen-7B UMA vez cada, com o MESMO prompt combinado,
  SEM retry e SEM loops de mínimo. Grava em results_data/results_N/<algo>/combined/<model>.txt.
- Bloco de chaves no topo: GROQ_API_KEY vazio (PASTE_YOUR_GROQ_KEY_HERE) injetado em os.environ;
  chaves iaedu já embebidas. Pré-req: internet (iaedu), GROQ_API_KEY, Ollama com qwen2.5-coder:7b.

### 10. Migração para outro PC
- Arquivo: `~/Documents/private/tese_migracao.tar.gz` (7.3M). Exclui .venv311 (venv Windows),
  __pycache__, .DS_Store, diogo/_unzipped. Inclui tudo o resto (results_data, algorithms_v3,
  scripts, apresentação, paper, versionControl.xlsx, chapters).
- `requirements.txt` criado (requests, aisuite, openpyxl, python-docx, groq). `.gitignore` criado.
- Git: só `changelog/` está ligado ao GitHub (repo `IntelligentSecureDistributedComputing/LLM-evaluation`).
  A RAIZ `tese/` tem um .git VAZIO sem remote; o trabalho principal NÃO estava versionado.
- No PC novo: extrair o tar.gz, criar venv, pip install -r requirements.txt, pôr GROQ_API_KEY
  no run_once.py, instalar Ollama + modelo.

### 11. Capítulos da tese (LaTeX, na raiz)
- `chapter_4.txt` (Evaluation): já tinha fases 1-5; foi ACRESCENTADA a secção final
  "Final Evaluation with the Unified Algorithm Set" com os 727 testes, as tabelas por modelo,
  por algoritmo (com fonte e erro), por propriedade, por modelo de falha, e as 3 causas dos 0%.
- `chapter_5.txt` (Conclusion): criado de raiz (resumo, findings, limitações, trabalho futuro).
- Os capítulos "oficiais" estão em `IST_UL_MSc_Dissertation/Chapters/Chapter_4.tex` e Chapter_5.tex
  (este último ainda é lorem ipsum). Os .txt da raiz podem ser copiados para lá.

## Ficheiros-chave
- `update_excel.py` (parser + Excel), `run_once.py`, `prompts/combined.txt`
- `algorithms_v3/`, `properties_v3/`, `prompts/`
- `diogo/analyze_diogo.py`, `diogo/gpt_reasons.py`, `diogo/make_presentation.py`, `diogo/make_summary_xlsx.py`
- `diogo/apresentacao_resultados.docx`, `diogo/resumo_resultados.xlsx`
- `chapter_4.txt`, `chapter_5.txt`, `rascunho-topicos-paper.tex`
- `changelog/README.md` (repo GitHub)
- `CONTEXT.md` (contexto geral anterior do projeto)

## Próximos passos em aberto
- Repor o agente do Claude na iaedu (ID novo) e voltar a correr esse modelo.
- Reforçar as corridas do LLaMA-70B (muitos erros por rate-limit do Groq).
- Preparar apresentação + artigo para a reunião de quinta 15h30.
- Consolidar as tabelas novas (fonte, tipo de erro, modelo de falha) também no paper.
- Colar a GROQ_API_KEY no run_once.py antes de perder o acesso a este PC.
