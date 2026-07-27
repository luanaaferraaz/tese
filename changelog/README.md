# Changelog

Registo das alterações mais relevantes entre fases. Nem todas as mudanças intermédias estão aqui — ao longo das iterações, os algoritmos e prompts foram sendo ajustados incrementalmente (reformulações de frases, correcções de formatação, ajustes nos thresholds descritos, clarificação de assunções) e as versões anteriores foram sobrepostas sem guardar cópia. As versões preservadas nesta pasta são os pontos de partida (v0), os estados antes das últimas correcções significativas (v1), e as versões corrigidas actuais (v2). Existiram versões intermédias entre eles que não foram guardadas. As decisões com maior impacto nos resultados estão documentadas abaixo.

---

## Algoritmos — Referências e Variações

| Algoritmo | Referência | Variações no changelog |
|-----------|-----------|----------------------|
| best-effort-broadcast | Cachin, Guerraoui, Rodrigues (2011) | v0 |
| reliable-broadcast | Cachin, Guerraoui, Rodrigues (2011) | v0, v1, v2 |
| echo-broadcast | Bracha (1987) | v0, v1, v2 |
| termination-reliable-broadcast | Hadzilacos and Toueg (1994) | v0 |
| reliable-broadcast-general-omission | Hadzilacos and Toueg (1989/1994) | v0, v1, v2 |
| termination-reliable-broadcast-general-omission | Hadzilacos and Toueg (1994) | v0 |
| byzantine-rb | Vaz, Matos, Pardal, Correia (IEEE Access) | v1, v2 |
| rb-crash-failure | Vaz, Matos, Pardal, Correia (IEEE Access) | — |
| fault-tolerant-rb-no-failure | Vaz, Matos, Pardal, Correia (IEEE Access) | v0 |
| new-byzantine-rb | Vaz, Matos, Pardal, Correia (IEEE Access) | — |

Algoritmos sem variações no changelog (rb-crash-failure, new-byzantine-rb) não tiveram alterações significativas entre as fases ou não se preservou a versão anterior.

---

## Ficheiros nesta pasta

```
algorithms/
  v0_*  — versões iniciais (da literatura, formato variável, com referência)
  v1_*  — template padronizado de 13 secções, antes das correcções da fase 5
  v2_*  — versões corrigidas (fase 5): guards explícitos, distinct sender, argumentos expandidos

prompts/
  v0_*  — prompt inicial (verbosa, sem restrição de formato)
  v1_*  — few-shot com exemplos (eliminada após fase 1)
  v2_*  — set final de 4 prompts (formato restrito, max 20 palavras)
  v3_*  — mesmas com pedido de confidence score (X/10)
```

Versões actuais (em uso): `../algorithms copy/` (algoritmos), `../prompts/` (prompts), `../prompts_confidence/` (com confidence)

---

## Fase 0 (antes da avaliação)

Algoritmos escritos a partir da literatura, cada um com referência bibliográfica no topo, formato variável entre eles. Prompt única, verbosa, com role-assignment e sem restrição de formato na resposta. Propriedades incluídas dentro da descrição do algoritmo, sem ficheiro separado.

Notado: modelos avaliavam dimensões não pedidas (complexidade, liveness, eficiência) e produziam prosa longa em vez de vereditos estruturados.

---

## Fase 1 (V0–V13)

Algoritmos reescritos para template uniforme de 13 secções. Removidas referências bibliográficas para reduzir input. Criada pasta `properties/` separada com apenas os nomes das propriedades a verificar. Adicionados novos algoritmos (byzantine-rb, rb-crash-failure, new-byzantine-rb, variantes general-omission).

Entre a fase 0 e a versão final da fase 1, os algoritmos passaram por várias reformulações intermédias que não estão preservadas: ajustes na linguagem das secções de system model e correctness argument, clarificação de variáveis locais, padronização dos nomes das mensagens, e pequenas correcções à descrição dos thresholds.

Prompts: adicionada few-shot com exemplos (V1), depois eliminada por ficar abaixo de 50%. Criado set final de 4 prompts com output restrito a uma linha por propriedade, max 20 palavras na razão. Também aqui houve versões intermédias das prompts (variações no texto das instruções, diferentes níveis de detalhe) que foram sobrepostas antes de se estabilizar no formato final.

Modelos: eliminados Phi-2 (2.6%), DeepSeek-Coder (49%), Yi-Coder (55%), GPT-4o (rate-limits). Mantido Qwen2.5-Coder-7B.

---

## Fase 2 (V19–V26)

Criadas 3 variantes de metadata do new-byzantine-rb (-n nome alterado, -o fault model alterado, -p propriedade trocada para Termination) para testar se o modelo analisa lógica ou texto superficial. Pseudocódigo idêntico ao original em todas.

Nenhuma alteração a prompts ou modelos.

---

## Fase 3 (V28–V39)

Adicionados modelos maiores via API: LLaMA-3.3-70B-Groq, DeepSeek-Chat V3, Gemini-2.5-Flash-Lite. Vários outros tentados mas nunca responderam (Gemini-2.5-Pro, DeepSeek-V4-Pro, DeepSeek-R1).

Nenhuma alteração a algoritmos ou prompts.

---

## Fase 4 (V41–V46)

Criadas 3 variantes com erros genuínos no pseudocódigo (-v threshold de trigger subido, -i threshold de delivery descido, -a forwarding removido).

Nenhuma alteração a prompts ou modelos.

---

## Fase 5 (V47–V79+)

Adicionados GPT-5.5 e Claude Opus 4 via plataforma iaedu. Resolvido problema de context limit (uuid novo por thread). Rate-limit ~1 run/dia.

Adicionadas prompts com pedido de confidence score (X/10) para verificar se confiança correlaciona com erros.

Corrigidas ambiguidades nos templates dos algoritmos onde os modelos grandes identificaram problemas legítimos (versões v1 → v2):

| Algoritmo | Problema no v1 | Correcção no v2 |
|-----------|---------------|----------------|
| echo-broadcast | Sem guard de `delivered` na delivery rule; counters não especificam distinct sender; typo "Timingyes" | Guards explícitos adicionados; validation rules de distinct sender; typo corrigido; invariants e correctness argument expandidos |
| reliable-broadcast | Self-deliver sem marcar `delivered` primeiro | Adicionado `delivered = delivered ∪ {m}` antes de `rb_deliver(m)` |
| reliable-broadcast-general-omission | Sem `if m ∉ delivered` no broadcast path | Guard adicionado antes de self-deliver |
| byzantine-rb | Argumento de Integrity vago ("cannot create enough support alone") | Cálculo numérico explícito: threshold=ceil(2.5)=3, Byzantine produz max 2, insuficiente |

Repostas referências bibliográficas em todos os algoritmos (tinham sido removidas na fase 1).

Não alterados: fault-tolerant-rb-no-failure, rb-crash-failure, best-effort-broadcast (erros dos modelos nestes são de raciocínio, não de ambiguidade no template).
