# Tópicos Reunião — 7 Julho 2025

## Contexto (última reunião)

Na reunião anterior apresentei os resultados até V53: os modelos grandes (GPT-5.5, Claude Opus 4) tinham detetado 100% dos erros nos algoritmos com pseudocódigo incorreto (V47, 17 respostas válidas). Porém, V48–V53 falharam todos por context limit. Fiquei de resolver essa questão.

---

## 1. O que fiz desde a última reunião

- **Resolvi o context limit**: era causado por usar o mesmo `thread_id` em todas as chamadas — a conversação acumulava e excedia o token budget. Fix: gerar um thread novo (UUID) por pedido.
- **Deparei-me com rate limit**: a plataforma iaedu permite ~1 run completa por dia. Espera de ~24-48h entre runs.
- **Reduzi a amostra**: em vez de testar todos os 10 algoritmos (que esgota a quota), seleccionei um subconjunto para poder repetir os mesmos testes e avaliar consistência.
- **Obtive resultados nos algoritmos corretos** (V59, V63, results_1_miguel) — é aqui que surgem os novos achados.

---

## 2. O novo achado: modelos grandes produzem falsos negativos

Na reunião anterior, o resultado era promissor: 100% de deteção de erros. Agora que testei nos algoritmos **corretos**, o quadro é diferente:

### Em algoritmos com erros no pseudocódigo (V47 — mesmos dados da reunião anterior):
- **GPT-5.5: 11/11 = 100% deteção** ✓
- **Claude Opus 4: 6/6 = 100% deteção** ✓

### Em algoritmos corretos (NOVO — V59 + V63 + results_1_miguel):
- **GPT-5.5: 32/63 = 50.8%** ✗
- **Claude Opus 4: 18/58 = 31.0%** ✗

Os modelos **marcam propriedades como violadas em algoritmos que estão corretos**.

### Assimetria completa com modelos pequenos:
| | Algoritmos corretos | Algoritmos com erros |
|---|---|---|
| **Modelos pequenos** (Qwen, LLaMA, DeepSeek) | ~95% ✓ | 0% ✗ |
| **Modelos grandes** (GPT-5.5, Claude Opus 4) | ~50% ✗ | 100% ✓ |

---

## 3. Padrão dos falsos negativos

O GPT-5.5 é **binário por algoritmo** — ou acerta 100% ou falha 100%, de forma consistente:

| Algoritmo | GPT-5.5 | Claude Opus 4 |
|---|---|---|
| best-effort-broadcast | **100%** ✓ | 89% |
| fault-tolerant-rb-no-failure | **100%** ✓ | 0% ✗ |
| rb-crash-failure | **100%** ✓ | 67% |
| byzantine-rb | **0%** ✗ | 56% |
| echo-broadcast | **0%** ✗ | 0% ✗ |
| reliable-broadcast-general-omission | 38% ✗ | 17% ✗ |

### Exemplo concreto — a mesma justificação, certa vs errada:

**No algoritmo ERRADO (-i, delivery threshold=1):**
```
RB-Integrity - [non satisfied]: Byzantine type1 can cause delivery of 
an unbroadcast message.
```
→ ✓ CORRETO (com threshold=1, um único Byzantine de facto consegue forçar delivery)

**No algoritmo CORRETO (byzantine-rb, delivery threshold=(n+f)/2):**
```
RB-Integrity - [non satisfied]: Byzantine process can trigger delivery
of an unbroadcast message.
```
→ ✗ ERRADO (o threshold (n+f)/2 impede isto — mas o modelo não verifica que o threshold é suficiente)

**Interpretação:** O modelo identifica o vetor de ataque correto mas não completa o raciocínio de que o quorum/threshold do algoritmo é suficiente para o prevenir. Faz verificação de ataques mas não faz verificação de defesas.

---

## 4. Análise por propriedade (todos os modelos, 2877 testes totais)

| # | Propriedade | Accuracy (corretos) | Observação |
|---|---|---|---|
| 1 | Termination | 100% | Nunca falha |
| 2 | RB-Validity | 99.5% | Quase perfeita |
| 3 | RB-Integrity | 96.7% | Boa |
| 4 | RB-Agreement | 93.3% | Moderada |
| 5 | No duplication | 91% | Fraca |
| 6 | No creation | 87.8% | A pior |

- Propriedades com terminologia standard (RB-*) são mais fáceis
- echo-broadcast é o algoritmo mais difícil para todos os modelos
- Há diferenças por prompt: chain-of-thought melhor para Agreement, role-based para Integrity

---

## 5. Perguntas / Decisões

1. **O resultado "permissivo vs restritivo" é interessante como conclusão?**
   - Modelos pequenos = bons a confirmar, não detetam erros (demasiado permissivos)
   - Modelos grandes = detetam erros, mas marcam corretos como errados (demasiado restritivos)
   - Nenhum modelo faz verificação formal fiável sozinho

2. **Vale a pena tentar melhorar os falsos negativos dos modelos grandes?**
   - Opção A: prompt adversarial ("Only mark non-satisfied if you can construct a concrete counterexample with specific n and f values")
   - Opção B: remover a secção de Correctness Argument do template
   - Opção C: aceitar o resultado como está

   **Análise das justificações — há padrões claros e corrigíveis por prompt:**

   As justificações dos falsos negativos caem em 5 categorias:

   | Categoria | Exemplo | Algoritmo afetado | Porquê está errado |
   |---|---|---|---|
   | **Threshold não verificado** | "Byzantine can trigger delivery of unbroadcast message" | byzantine-rb | O modelo vê o ataque mas ignora que threshold=(n+f)/2 o previne |
   | **Guard assumida em falta** | "Delivery rule lacks a delivered guard" | echo-broadcast | O modelo não encontra o `delivered` check no pseudocódigo (pode ser implícito ou noutro formato) |
   | **Duplicação Byzantine** | "Counters are not restricted to distinct senders" | echo-broadcast | O modelo assume que contadores aceitam duplicados quando o algoritmo filtra por sender |
   | **Crash mid-send** | "If it crashes mid-send, some may never receive" | fault-tolerant-rb | O modelo ignora que o algoritmo assume no-failure model |
   | **Self-delivery** | "Broadcaster never delivers to itself" | fault-tolerant-rb | O modelo assume que o broadcaster precisa de se auto-entregar |

   **Conclusão**: O modelo identifica vetores de ataque legítimos mas não completa o raciocínio verificando que as defesas (thresholds, guards, model assumptions) os previnem.

   **Prompt sugerido para corrigir:**
   ```
   For each property, first identify the specific mechanism in the pseudocode 
   that guarantees it (threshold value, guard condition, model assumption). 
   Only mark non-satisfied if no such mechanism exists OR if you can construct 
   a concrete counterexample with specific values of n and f that violates the 
   property despite the mechanism.
   ```

   Isto forçaria o modelo a:
   1. Encontrar a defesa antes de declarar violação
   2. Dar um contraexemplo concreto (que não vai conseguir para algoritmos corretos)

3. **Os dados são suficientes para fechar?**
   - 2877 testes, 18 modelos, 16 algoritmos, 5 prompts
   - A narrativa é clara, mas poderia ser mais forte com mais runs dos modelos grandes

4. **Acesso direto à API OpenAI/Anthropic resolveria o rate limit** — é possível?
