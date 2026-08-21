#!/usr/bin/env python3
"""Word document for the meeting — last two weeks of work.

Style follows the user's manual choices:
  - single simple titles: normal font, size 15, bold, no numbers, no underline
  - no grey subtitle lines, no italic asides
  - suggestions written as organic prose (no per-suggestion subtitles)
  - "Diogo" (not "Prof. Diogo")
  - new algorithms mentioned without stating their final names/properties
  - prompts described only as a template change
  - "modelos com maior potencial" (never "modelos de fronteira")
Keeps the three tables requested by the professor (source column, error-type
column, and a per-fault-model table).
"""
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = Path(__file__).resolve().parent / "apresentacao_resultados.docx"

BLACK = RGBColor(0x00, 0x00, 0x00)

doc = Document()
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(12)


def shade_cell(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def set_cell_text(cell, text, bold=False, align="left", size=11, white=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT,
                   "center": WD_ALIGN_PARAGRAPH.CENTER}[align]
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if white:
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def heading(text):
    """Simple title: normal font, size 15, bold, black. No number, no border."""
    p = doc.add_paragraph()
    p.space_before = Pt(10)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(15)
    run.font.color.rgb = BLACK
    return p


def subheading(text):
    p = doc.add_paragraph()
    p.space_before = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = BLACK
    return p


def body(text, size=12):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p


def bullet(text, level=0, lead=None):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    if lead:
        r = p.add_run(lead)
        r.bold = True
    p.add_run(text)
    return p


def make_table(headers, rows, colcolors=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for j, h in enumerate(headers):
        shade_cell(hdr[j], "404040")
        set_cell_text(hdr[j], h, bold=True, align="center", white=True, size=11)
    for row in rows:
        cells = t.add_row().cells
        for j, val in enumerate(row):
            fill = colcolors(j, val) if colcolors else None
            if fill:
                shade_cell(cells[j], fill)
            set_cell_text(cells[j], val, bold=(j == 0),
                          align="left" if j == 0 else "center", size=11)
    return t


def perf_color(j, val):
    if j == 0:
        return None
    try:
        num = int(val.split("%")[0])
    except Exception:
        return None
    if num >= 80:
        return "C6EFCE"
    if num >= 50:
        return "FFEB9C"
    return "FFC7CE"


def code_block(text):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F2F2F2")
    pPr.append(shd)
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    return p


# ── Título simples ─────────────────────────────────────────────
heading("Ponto de situação — últimas duas semanas")

# ── Contexto ───────────────────────────────────────────────────
heading("Contexto")
body("Nas fases anteriores tinha ficado clara uma assimetria entre classes de modelos: os modelos "
     "pequenos e médios (Qwen-7B, LLaMA-70B, DeepSeek) confirmam bem os algoritmos corretos mas quase "
     "não detetam erros no pseudocódigo, enquanto os modelos com maior potencial (GPT-5.5, Claude) "
     "detetam os erros mas rejeitam muitos algoritmos corretos. Foi sobre este ponto que o Diogo deu "
     "um conjunto de sugestões, e as últimas duas semanas foram dedicadas a implementá-las e a voltar "
     "a testar.")

# ── Sugestões (prosa orgânica, sem subtítulos) ─────────────────
heading("As sugestões do Diogo e o que fiz")
body("Comecei por deixar de lado os algoritmos que o Diogo sugeriu ignorar, os de Terminating Reliable "
     "Broadcast, por serem mais difíceis e próximos de Consenso, e ainda o new-byzantine-rb e o "
     "byzantine-rb, que tinham uma pequena falha, retirando-os do conjunto de testes. Depois acrescentei "
     "os dois Reliable Broadcast Bizantinos que ele indicou, o de Bracha e o de Imbs e Raynal, e ainda "
     "um Uniform Reliable Broadcast do livro do Cachin, tolerante a falhas por crash, criando também "
     "uma variante com erro para este último.")
body("Encurtei os prompts, que estavam demasiado verbosos, mudando os templates para uma versão mais "
     "simples. E, por fim, unifiquei o pseudocódigo de todos os algoritmos para ficarem muito parecidos "
     "entre si e reduzir as pistas superficiais no texto. As diferenças concretas entre o template "
     "antigo e o novo estão a seguir.")

# ── Template antigo vs novo ────────────────────────────────────
heading("Template antigo vs. novo")
body("O template antigo tinha até 13 secções e incluía informação que dava pistas ao modelo. O novo "
     "tem 7 secções e é neutro e uniforme. As diferenças principais:")
make_table(
    ["Aspeto", "Template antigo", "Template novo"],
    [
        ["Nº de secções", "13 secções", "7 secções"],
        ["Nome / referência", "Incluía o nome do algoritmo e a referência bibliográfica no topo",
         "Sem nome nem referência (só \"Problem type\")"],
        ["Secções extra", "Interface (API), Message Types, Decision/Delivery Rule separadas",
         "Integradas no pseudocódigo"],
        ["Estado local", "Variáveis específicas por algoritmo (sent_echo, sent_ready, delivered)",
         "Estado comum a todos (msg_sent, msg_received, delivered_value)"],
        ["Tipos de mensagem", "Nomes reveladores (SEND, ECHO, READY)",
         "Genéricos (type0, type1, type2)"],
        ["Pressupostos", "Espalhados pelo texto",
         "Subsecção \"Assumptions\" explícita e igual em todos"],
    ],
)
subheading("Exemplo concreto (echo-broadcast, tratamento da 1ª mensagem)")
body("Antigo:", size=11)
code_block(
    "on receive SEND(m) from Sender:\n"
    "    if sent_echo is false:\n"
    "        sent_echo ← true\n"
    "        send ECHO(m) to all processes."
)
body("Novo:", size=11)
code_block(
    "upon receive(<type0, m>) from pj:\n"
    "    msg_received ← msg_received ∪ {<type0, m>}\n"
    "    if not already sent <type1, m>:\n"
    "        send <type1, m> to all processes\n"
    "        msg_sent ← msg_sent ∪ {<type1, m>}"
)

# ── Os testes ──────────────────────────────────────────────────
heading("Os testes desta ronda")
body("Tentei testar cinco modelos: GPT-5.5 e Claude (via iaedu), LLaMA-70B, DeepSeek e Qwen-7B. Dois "
     "não produziram dados aproveitáveis:")
bullet("DeepSeek: falhou sempre por falta de créditos na API. Zero resultados válidos, ficou de fora.")
bullet("Claude (iaedu-model-2): desapareceu da iaedu. O agente já não aparece na minha conta e todos "
       "os testes deram erro, tanto com as minhas credenciais como com as do Prof. Miguel.")
body("Descontando estes dois, ficaram 727 testes válidos distribuídos pelos outros três modelos. Uma "
     "nota sobre a métrica, para os números não enganarem: um algoritmo correto só conta como verificado "
     "(accuracy) se o modelo marcar todas as propriedades como satisfeitas; uma variante com erro conta "
     "como detetada se marcar pelo menos uma propriedade como violada.")

# ── Resultados por modelo ──────────────────────────────────────
heading("Resultados por modelo")
make_table(
    ["Modelo", "Testes válidos", "Accuracy (corretos)", "Deteção (com erro)"],
    [
        ["GPT-5.5", "167", "38% (41/107)", "100% (60/60)"],
        ["LLaMA-3.3-70B", "280", "91% (164/180)", "80% (80/100)"],
        ["Qwen-2.5-Coder-7B", "280", "77% (139/180)", "90% (90/100)"],
    ],
)
body("")
bullet("detetou 90% das variantes com erro, mantendo 77% de acerto nos corretos e sem uma única falha "
       "de API. É muito diferente das fases anteriores, em que o Qwen quase não detetava os erros. A "
       "reestruturação dos prompts e a uniformização do pseudocódigo parecem ter ajudado bastante os "
       "modelos pequenos.", lead="Qwen (pequeno): ")
bullet("deteta 100% dos erros, mas é excessivamente desconfiado e marca como incorretos vários "
       "algoritmos que estão certos, ficando com apenas 38% de acerto nos corretos.", lead="GPT-5.5: ")

# ── Resultados por algoritmo ───────────────────────────────────
heading("Resultados por algoritmo")
body("Para ver se há um padrão por algoritmo. Percentagem de acerto por modelo (verde alto, amarelo "
     "médio, vermelho baixo).")

subheading("Algoritmos corretos — accuracy (com a fonte de cada algoritmo)")
make_table(
    ["Algoritmo", "Fonte", "GPT-5.5", "LLaMA-70B", "Qwen-7B"],
    [
        ["best-effort-broadcast", "Cachin et al. (2011)", "0% (0/12)", "75% (15/20)", "65% (13/20)"],
        ["reliable-broadcast", "Cachin et al. (2011)", "100% (12/12)", "70% (14/20)", "50% (10/20)"],
        ["reliable-broadcast-gen-omission", "Hadzilacos & Toueg (1994)", "92% (11/12)", "100% (20/20)", "65% (13/20)"],
        ["echo-broadcast", "Bracha (1987)", "0% (0/12)", "100% (20/20)", "70% (14/20)"],
        ["bracha-byzantine-rb", "Bracha (1987)", "0% (0/12)", "100% (20/20)", "85% (17/20)"],
        ["imbs-byzantine-rb", "Imbs & Raynal", "0% (0/12)", "100% (20/20)", "70% (14/20)"],
        ["rb-crash-failure", "Vaz et al. (IEEE Access)", "0% (0/12)", "100% (20/20)", "90% (18/20)"],
        ["fault-tolerant-rb-no-failure", "Vaz et al. (IEEE Access)", "92% (11/12)", "100% (20/20)", "100% (20/20)"],
        ["uniform-reliable-broadcast", "Cachin et al. (2011), §3.4.3", "64% (7/11)", "75% (15/20)", "100% (20/20)"],
    ],
    colcolors=lambda j, v: perf_color(j - 1, v) if j >= 2 else None,
)

subheading("Variantes com erro — deteção (com o tipo de erro introduzido)")
make_table(
    ["Variante", "Tipo de erro introduzido", "GPT-5.5", "LLaMA-70B", "Qwen-7B"],
    [
        ["best-effort-broadcast_B", "Envia a todos exceto a si próprio (devia incluir-se)",
         "100% (12/12)", "75% (15/20)", "95% (19/20)"],
        ["reliable-broadcast_B", "Passo de relay removido (quebra Agreement)",
         "100% (12/12)", "100% (20/20)", "100% (20/20)"],
        ["echo-broadcast_B", "Regra de amplificação f+1 READY removida (quebra Agreement)",
         "100% (12/12)", "100% (20/20)", "90% (18/20)"],
        ["imbs-byzantine-rb_B", "Limiar (n+f)/2 em vez de (n+f+1)/2 (quórum enfraquecido)",
         "100% (12/12)", "25% (5/20)", "80% (16/20)"],
        ["uniform-reliable-broadcast_B", "Entrega com 1 ACK em vez de > n/2 (quebra Uniform Agreement)",
         "100% (12/12)", "100% (20/20)", "85% (17/20)"],
    ],
    colcolors=lambda j, v: perf_color(j - 1, v) if j >= 2 else None,
)
body("")
bullet("O GPT-5.5 mostra um padrão binário: acerta a 100% em reliable-broadcast, fault-tolerant e "
       "general-omission, mas cai a 0% em best-effort, echo, bracha, imbs e rb-crash. São os algoritmos "
       "com relay/quórum, onde imagina ataques e chumba o algoritmo.")
bullet("O LLaMA-70B é sólido nos corretos, mas na deteção falha claramente no imbs-byzantine-rb_B (25%).")
bullet("O Qwen é o mais equilibrado, com bom desempenho nas duas tarefas.")

# ── Porque os 0% do GPT ────────────────────────────────────────
heading("Porque é que o GPT-5.5 dá 0% nesses algoritmos")
body("Os 0% não são recusas de resposta. O GPT responde sempre, mas marca sempre pelo menos uma "
     "propriedade como violada, com raciocínios errados mas consistentes. Há três causas distintas.")

subheading("Causa A — lê mal o fluxo dos tipos de mensagem (best-effort)")
body("No best-effort-broadcast falha sempre a Validity, convencido de que as mensagens nunca são "
     "entregues, porque se baralha com os nomes genéricos type0/type1 e acha que a entrega espera por "
     "um tipo que nunca é enviado. Citações reais:")
bullet("\"Processes send type0 but delivery requires type1, so correct processes may never deliver.\"", level=1)
bullet("\"delivery waits for type1, but broadcasts send only type0\"", level=1)
body("Isto sugere que a uniformização dos nomes de mensagem (type0/type1/type2) pode estar a prejudicar "
     "o GPT neste algoritmo simples, por lhe tirar as pistas semânticas (SEND, ECHO) que antes o "
     "ajudavam a seguir o fluxo.")

subheading("Causa B — vê um ataque mas não verifica que o quórum o impede (echo, bracha, imbs)")
body("Nos algoritmos Bizantinos com relay e quórum, identifica sempre um vetor de ataque e nunca "
     "confirma que os limiares o bloqueiam. Citações reais:")
bullet("Integrity: \"Byzantine non-broadcaster can inject type0, causing delivery of a value never "
       "broadcast.\"", level=1)
bullet("Validity: \"Byzantine type0 can be delivered before a correct broadcaster's message.\"", level=1)
bullet("Agreement: \"Correct processes may ECHO and READY multiple values, so different processes can "
       "deliver different first values.\"", level=1)

subheading("Causa C — raciocina fora do modelo assumido (rb-crash-failure)")
body("Inventa cenários que contrariam a condição de resiliência ou os pressupostos do algoritmo. "
     "Citações reais:")
bullet("Validity: \"Threshold f+1 may exceed number of correct processes when N ≤ 2f.\"", level=1)
bullet("Agreement: \"A faulty process can send type1 to one correct process then crash, leaving others "
       "below threshold.\"", level=1)

# ── Falsos positivos por propriedade ───────────────────────────
heading("De onde vêm os falsos positivos do GPT-5.5")
body("Nos algoritmos corretos, quantas vezes cada modelo marcou erradamente cada propriedade como "
     "violada (quanto maior, pior).")


def fp_color(j, val):
    if j == 0:
        return None
    try:
        num = int(val.split("%")[0])
    except Exception:
        return None
    if num >= 30:
        return "FFC7CE"
    if num >= 10:
        return "FFEB9C"
    return "C6EFCE"


make_table(
    ["Propriedade", "GPT-5.5", "LLaMA-70B", "Qwen-7B"],
    [
        ["Validity",          "43% (46/107)", "0% (0/180)",  "5% (9/180)"],
        ["Integrity",         "50% (24/48)",  "0% (0/80)",   "5% (4/80)"],
        ["Agreement",         "40% (34/84)",  "4% (6/140)",  "16% (23/139)"],
        ["Uniform Agreement", "36% (4/11)",   "25% (5/20)",  "0% (0/20)"],
        ["No creation",       "22% (13/59)",  "5% (5/100)",  "5% (5/100)"],
        ["No duplication",    "0% (0/59)",    "0% (0/100)",  "10% (10/100)"],
    ],
    colcolors=fp_color,
)
body("")
bullet("Os falsos positivos do GPT-5.5 concentram-se nas propriedades que exigem raciocinar sobre "
       "todas as execuções e sobre o adversário (Validity, Integrity, Agreement). Numa propriedade "
       "local como No duplication, nunca erra.")
bullet("O LLaMA-70B é o oposto: quase nunca marca uma propriedade como violada, o que lhe dá alta "
       "accuracy mas também explica a menor deteção nas variantes com erro.")
bullet("O Qwen fica no meio, com falsos positivos espalhados mas todos baixos.")

# ── Por modelo de falha ────────────────────────────────────────
heading("Resultados por modelo de falha")
body("Agrupando os algoritmos pelo modelo de falha que assumem, para ver se há um padrão por tipo de "
     "falha (verde alto, amarelo médio, vermelho baixo).")

subheading("Algoritmos corretos — accuracy por modelo de falha")
make_table(
    ["Modelo de falha", "GPT-5.5", "LLaMA-70B", "Qwen-7B"],
    [
        ["Crash", "40% (19/47)", "80% (64/80)", "76% (61/80)"],
        ["Omissão geral", "92% (11/12)", "100% (20/20)", "65% (13/20)"],
        ["Bizantino", "0% (0/36)", "100% (60/60)", "75% (45/60)"],
        ["Sem falhas", "92% (11/12)", "100% (20/20)", "100% (20/20)"],
    ],
    colcolors=perf_color,
)

subheading("Variantes com erro — deteção por modelo de falha")
make_table(
    ["Modelo de falha", "GPT-5.5", "LLaMA-70B", "Qwen-7B"],
    [
        ["Crash", "100% (36/36)", "92% (55/60)", "93% (56/60)"],
        ["Bizantino", "100% (24/24)", "62% (25/40)", "85% (34/40)"],
    ],
    colcolors=perf_color,
)
body("")
bullet("O modelo de falha explica bem os 0% do GPT-5.5: nos algoritmos Bizantinos corretos cai a 0%, "
       "porque é aí que imagina ataques e chumba o algoritmo. Nos modelos de falha mais simples "
       "(omissão e sem falhas) sobe para 92%.")
bullet("Na deteção, o GPT-5.5 mantém 100% em ambos. O LLaMA e o Qwen são sólidos nos crash mas descem "
       "nos Bizantinos, sobretudo o LLaMA (62%), puxado pelo imbs-byzantine-rb_B.")

# ── Leitura e próximos passos ──────────────────────────────────
heading("Leitura e próximos passos")
bullet("Mantém-se a assimetria entre classes de modelos, mas com uma novidade positiva: com os prompts "
       "reestruturados e o pseudocódigo uniformizado, o Qwen (pequeno) passou a detetar 90% dos erros, "
       "o que abre uma via interessante.")
bullet("O GPT-5.5 continua a ser o melhor a detetar erros, mas é preciso perceber e mitigar os falsos "
       "positivos nas propriedades de segurança, sobretudo nos algoritmos com relay e quórum.")
body("")
subheading("Próximos passos")
bullet("Assim que o agente do Claude voltar a estar disponível na iaedu (não depende de mim), voltar a "
       "correr esse modelo, que é peça central da comparação.")
bullet("Reforçar as corridas do LLaMA-70B, que teve muitos erros por rate-limit do Groq, para uma base "
       "estatística mais sólida.")
bullet("Consolidar tudo no artigo e cruzar, por propriedade, a deteção com o erro real de cada variante.")

doc.save(OUT)
print(f"Saved {OUT}")
