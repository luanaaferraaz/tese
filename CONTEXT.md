# Thesis Project Context

## What this project is

Master's thesis at IST (Instituto Superior Técnico, Universidade de Lisboa) evaluating whether Large Language Models can verify correctness properties of distributed broadcast algorithms. The thesis explores LLMs as complementary/alternative tools to traditional formal verification (theorem proving, model checking).

**Research question**: Can Language Models support or complement the verification of distributed algorithms by reasoning over their descriptions and correctness properties?

## Supervisors
- Professor Diogo (main supervisor, has iaedu platform access)
- Professor Miguel (co-supervisor, sometimes misses meetings)

## Thesis Document Structure
Located at: `/Users/lourelua/Documents/private/tese/IST_UL_MSc_Dissertation/`
- **Chapter 1** (Introduction): Motivation, objectives, contributions — DONE
- **Chapter 2** (Background): Distributed algorithms, LMs, verification, benchmarking — DONE (not checked)
- **Chapter 3** (Implementation): System architecture, algorithm templates, prompt design, model interface — DONE
- **Chapter 4** (Evaluation): Results — PARTIAL DRAFT (covers V0–V43, needs update with V44–V71 + iaedu findings)
- **Chapter 5** (Conclusions): Template placeholder only — NOT STARTED
- PDF output: `/Users/lourelua/Documents/private/tese/IST_UL_MSc_Dissertation.pdf`

## Platform: iaedu
- API at `https://api.iaedu.pt/agent-chat/`
- Provides access to **GPT-5.5** (`iaedu-model-1`) and **Claude Opus 4** (`iaedu-model-2`)
- Daily rate limit (~1 full test run per day, ~24h wait between runs)
- Requires unique `thread_id` per request (using `uuid.uuid4()`) to avoid context accumulation
- Script: `script-2.py`

## Project File Structure

```
/Users/lourelua/Documents/private/tese/
├── IST_UL_MSc_Dissertation/     # LaTeX source
├── algorithms/                  # Algorithm descriptions (input to models)
│   ├── new-byzantine-rb-n.txt   # Variant: wrong name (not a real error)
│   ├── new-byzantine-rb-o.txt   # Variant: wrong fault model label (not real error)
│   ├── new-byzantine-rb-p.txt   # Variant: wrong property (Termination instead of Integrity)
│   ├── new-byzantine-rb-v.txt   # BROKEN: threshold for type0→type1 raised to f+1 (breaks Validity)
│   ├── new-byzantine-rb-i.txt   # BROKEN: delivery threshold lowered to 1 (breaks Integrity)
│   └── new-byzantine-rb-a.txt   # BROKEN: forwarding rule removed (breaks Agreement)
├── algorithms copy/             # Original correct algorithms (10 algorithms)
├── properties/                  # Expected properties per algorithm (comma-separated)
├── properties copy/             # Same but used by update_excel.py
├── prompts/                     # Current prompt templates (4: chain_of_thought, role_based, strict_format, zero_shot)
├── prompts_confidence/          # Same prompts but requesting confidence score (X/10)
├── prompts/older/               # Archived: few_shot, initial_prompt
├── results/ to results_71/      # Versioned results
├── results_1_miguel to results_6_miguel  # Runs from Miguel's machine
├── tese(1) 2/                   # Contains results_40 to results_43
├── script-2.py                  # Main experiment runner
├── update_excel.py              # Generates versionControl.xlsx with all analysis
├── versionControl.xlsx          # Output: all results, comparisons, property analysis
├── reuniao-topicos.md           # Meeting notes
└── CONTEXT.md                   # This file
```

## Key Results (as of July 2025)

### Total numbers
- ~3500+ tests total, 71+ versions, 18 models, 16 algorithms, 5 prompts
- Significant portion are errors/timeouts (especially iaedu rate limits, GPT-4o)

### Phase 1: SLMs (V0–V13)
- Qwen2.5-Coder-7B: **94.5%** cumulative (deterministic, best SLM)
- DeepSeek-Coder-6.7B: 49% (probabilistic, eliminated V13)
- Yi-Coder-9B-Chat: 55.2% (unstable, eliminated V13)
- Phi-2: 2.6% (eliminated V5)
- GPT-4o: 100% when responding but constant rate-limits (eliminated)
- Few-shot prompt: eliminated (<50%)

### Phase 2: Metadata variants (V19–V37)
- -n (wrong name): Qwen 97% — models evaluate logic, not names
- -o (wrong fault label): Qwen 100%
- -p (wrong property - Termination): Qwen 82%, LLaMA-70B 50%, DeepSeek-Chat 75%

### Phase 3: Pseudocode errors + medium models (V38–V53)
- Created -v (breaks Validity), -i (breaks Integrity), -a (breaks Agreement)
- Medium models (LLaMA-70B, DeepSeek-Chat, Qwen-7B): **0% detection** on broken algorithms
- Same models: ~95-100% on correct algorithms
- Conclusion: SLMs/medium models cannot falsify, only confirm

### Phase 4: Large models via iaedu (V47 + V59–V71 + miguel_1–6)

**On broken algorithms (V47):**
- GPT-5.5: **11/11 = 100% detection**
- Claude Opus 4: **6/6 = 100% detection**
- Claude gives perfect answers (identifies only the violated property)

**On correct algorithms (V59–V71 + miguel_2–6, ~500 valid tests):**
- GPT-5.5: **61.5%** (152/247)
- Claude Opus 4: **26.8%** (64/239)
- Both produce many false negatives

### The asymmetry finding (MAIN RESULT):
| | Correct algorithms | Broken algorithms |
|---|---|---|
| Small/medium models | ~95% ✓ | 0% ✗ |
| Large models (GPT-5.5, Claude) | ~50-61% ✗ | 100% ✓ |

### GPT-5.5 is binary per algorithm:
- **Always correct**: best-effort-broadcast (100%), fault-tolerant-rb (100%), rb-crash-failure (100%)
- **Always wrong**: byzantine-rb (0%), echo-broadcast (0%), reliable-broadcast (0-17%)
- Pattern: identifies attack vectors but doesn't verify that thresholds/quorums prevent them

### Per-property analysis (correct algorithms, iaedu models):
| Property | Accuracy | Confidence when correct | Confidence when wrong |
|---|---|---|---|
| RB-Validity | 94.7% | 9.3 | 7.0 |
| Validity | 86.0% | 9.6 | 6.2 |
| RB-Agreement | 81.3% | 9.0 | 5.9 |
| RB-Integrity | 80.7% | 9.4 | 9.9 (!) |
| No creation | 78.9% | 9.1 | 7.8 |
| No duplication | 60.5% | 9.8 | 8.7 |
| Agreement | 56.1% | 9.0 | 7.6 |

### Confidence filter finding:
- **Claude Opus 4**: filtering by confidence ≥ 8 raises accuracy from 76.7% to **94.9%** (+18pp)
  - Agreement: 58% → 100%, Validity: 72% → 100%, RB-Agreement: 71% → 94%
- **GPT-5.5**: filter has almost no effect (+0.5pp) — model is confident even when wrong

### Models are complementary:
- GPT-5.5: 100% on RB-Validity and RB-Agreement, but 67% on RB-Integrity
- Claude: 99% on RB-Integrity, but 56% on RB-Agreement
- Combined they would achieve ~99% across all RB properties

## Scripts

### script-2.py
- Reads algorithms from `ALGORITHMS_DIR`
- Reads prompts from `PROMPTS_DIR`
- Reads properties from `PROPERTIES_DIR`
- Outputs to auto-incrementing `results_N/` folder
- Uses `uuid.uuid4()` for thread_id per request
- Has retry logic with exponential backoff for rate limits
- `time.sleep(15)` between iaedu calls

### update_excel.py
- Discovers all `results*/` folders automatically
- Parses result files (plain text and GPT JSON-stream format)
- Generates sheets: Results Comparison, Version N, Cumulative Success, Property Analysis
- Property Analysis sections: global ranking, per-model, per-algorithm, broken detection, prompt×property, prompt×property×model
- Run: `python3 update_excel.py`

## TODO / Next Steps

1. **More iaedu runs on broken algorithms** — only have V47 data (17 valid responses); need more to confirm 100% detection
2. **Test "defense-first" prompt** — force model to identify the mechanism that guarantees each property before declaring violation. Proposed prompt:
   ```
   For each property, first identify the specific mechanism in the pseudocode
   that guarantees it (threshold value, guard condition, model assumption).
   Only mark non-satisfied if no such mechanism exists OR if you can construct
   a concrete counterexample with specific values of n and f.
   ```
3. **Apply confidence filter systematically** — already shown to help Claude (+18pp); write up as a recommendation
4. **Write Chapter 4 sections 4.5–4.7** covering:
   - Pseudocode error tests and the asymmetry finding
   - Introduction of iaedu models (GPT-5.5, Claude Opus 4)
   - False negative analysis and confidence filtering
5. **Write Chapter 5** (Conclusions)
6. **Update CONTEXT.md** after each session

## Reminders for next session
- Confidence scoring already in `prompts_confidence/` — check if new results used them
- The `properties copy/` folder is what `update_excel.py` reads from
- iaedu-model-1 = GPT-5.5, iaedu-model-2 = Claude Opus 4
- Rate limit resets ~24h; plan runs accordingly
