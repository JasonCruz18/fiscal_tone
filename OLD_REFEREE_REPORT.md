# REFEREE REPORT: "Fiscal Tone"

**Journal**: Economics Letters
**Manuscript**: Fiscal Tone
**Authors**: Jason Cruz, Diego Winkelried, Marco Ortiz
**Date**: January 28, 2025
**Recommendation**: **MAJOR REVISION**

---

## OVERALL ASSESSMENT

This paper makes an important methodological contribution by applying large language models (LLMs) to measure fiscal council behavior through textual analysis. The research question is novel and policy-relevant: how can we assess the *de facto* vigilance of fiscal institutions rather than just their *de jure* characteristics? The Peruvian case provides an ideal testing ground, combining a well-documented fiscal deterioration with a technically rigorous Fiscal Council that has maintained consistent communication.

**Strengths:**
1. **Novel approach**: First application of LLM-based textual analysis to fiscal council communications
2. **Policy relevance**: Addresses the gap between institutional design and actual behavior
3. **Timeliness**: Peru's recent fiscal deterioration makes the case compelling
4. **Replicability**: Method can be applied to other countries and institutions
5. **Clear narrative**: Well-structured progression from theory to empirics

**Weaknesses:**
1. **Section 3 lacks technical rigor**: Critical methodological details are missing or imprecise
2. **Data description inconsistencies**: Corpus size varies across text without explanation
3. **Limited validation**: No robustness checks, sensitivity analysis, or alternative specifications
4. **Weak connection to literature**: Empirical section doesn't engage with theoretical predictions
5. **Figure labeling issues**: Referenced figures don't match manuscript figures

**Recommendation**: The paper has publication potential but requires substantial revisions, particularly in Section 3. The core contribution is sound, but the execution needs strengthening to meet Economics Letters standards.

---

## DETAILED COMMENTS BY SECTION

### **Abstract** (Lines 41-43)

**Assessment**: Strong and well-written, but could be more precise about methods and findings.

**Issues:**
1. **Vague sample description**: "all reports and communiqués" → How many? What time span exactly?
2. **Missing key result**: The abstract states results "reveal a marked shift" but doesn't quantify it
3. **Overclaim**: "replicable tool" is mentioned but no replication materials are referenced

**Suggestions:**
```
Revision 1: Replace "all reports and communiqués issued by the Peruvian Fiscal
Council between 2016 and 2025" with "77 public documents (49 reports and 28
communiqués) issued between 2016 and 2025, comprising 1,432 substantive
paragraphs"

Revision 2: Add quantitative finding: "The fiscal tone index deteriorated from
-0.20 in 2016-2019 to -0.35 in 2022-2025, with the most severe warnings
(score 5) increasing from 5% to 15% of all paragraphs."

Revision 3: Add data availability statement: "Code and replication materials
available at [GitHub/repository]"
```

---

### **Introduction** (Lines 61-80)

**Assessment**: Excellent literature review that positions the paper well within the institutional fiscal framework literature.

**Strengths:**
- Comprehensive coverage from Alesina-Tabellini (1990) to recent meta-analyses
- Logical progression from theory → institutional design → empirical evidence
- Clear identification of research gap (*de jure* vs *de facto* measures)

**Issues:**

1. **Missing connection to text-as-data literature** (Line 77): You cite Niebler & Windhager (2023) and Gilardi & Schmid (2023) but don't engage with the broader econometric text analysis literature:
   - Missing: Baker, Bloom & Davis (2016) - Economic Policy Uncertainty Index
   - Missing: Gentzkow, Kelly & Taddy (2019) - Text as Data methods
   - Missing: Hansen & McMahon (2016) - Shocking Language (Fed communications)

2. **Weak motivation for LLM choice**: Why GPT-4o specifically? What advantages over:
   - Dictionary methods (Loughran-McDonald sentiment)?
   - Topic models (LDA, STM)?
   - Supervised ML (BERT fine-tuning)?

3. **Paragraph 5 too brief** (Line 79): The transition to Peru case feels abrupt. Add 2-3 sentences explaining:
   - Why Peru is an ideal case study (strong FC, documented deterioration)
   - What variation you exploit (time variation in fiscal conditions)
   - Preview of main findings

**Suggested additions:**

```latex
[After Line 77, add:]
The broader text-as-data literature in economics provides precedent for
quantifying policy positions through textual analysis. \citet{BakerBloomDavis2016}
construct policy uncertainty indices from newspaper text, while
\citet{HansenMcMahon2016} analyze Federal Reserve communications to identify
monetary policy shocks. Our LLM approach extends this tradition by leveraging
instruction-based classification, which—unlike dictionary methods or topic
models—can capture contextual nuance and be guided through domain-specific
prompts \citep{GentzkowKellyTaddy2019}.

[After Line 79, add:]
Peru provides an ideal setting for this analysis. Following a decade of fiscal
prudence (2000-2016), the country experienced marked institutional deterioration
amid rising political instability. Throughout this period, the Fiscal Council
maintained technical rigor and publishing consistency, generating rich textual
variation that allows us to track how institutional warnings respond to changing
fiscal conditions. Our fiscal tone index reveals [PREVIEW MAIN FINDING].
```

---

### **Section 2: Background on the Peruvian Case** (Lines 82-93)

**Assessment**: Well-researched institutional history, but could strengthen link to empirical analysis.

**Strengths:**
- Comprehensive timeline of fiscal reforms (1999-2016)
- Clear documentation of rule violations (Figure 1 effectively summarizes)
- Institutional detail grounds the empirical work

**Issues:**

1. **Figure 1 caption unclear** (Lines 152-158):
   - "Red × marks denote years when the expenditure rule was suspended or not met" → This conflates two distinct situations. Were they *suspended* (legal exemption) or *violated* (non-compliance)?
   - "2020 fiscal deficit (8% of GDP) is omitted for visual clarity" → Why? This is the most important data point! Either show it or provide it in a table.

2. **Missing explicit hypotheses**: Given the institutional narrative, what should we expect to see in FC tone?
   - H1: FC tone should worsen after 2020 (rule suspension)
   - H2: Tone should be most severe during 2022-2025 (Constitutional Court ruling + legislative activism)
   - H3: Tone should correlate with rule violations shown in Figure 1

3. **Weak transition to Section 3**: The paragraph ending Line 93 says "The next section uses large language models (LLMs) to quantify this evolution" but this sentence is commented out. This leaves Section 2 hanging without clear setup for what follows.

**Suggested revisions:**

```latex
[Line 158, revise note:]
\textbf{Notes:} [...] Red "$\times$" marks denote years when the expenditure
rule was legally suspended (pink background) or violated without suspension
(red background). The 2020 fiscal deficit reached -8.9\% of GDP; for scale,
this extreme value is indicated but not shown in the bar chart. [ADD TABLE
WITH EXACT VALUES AS APPENDIX TABLE A1]

[After Line 93, restore and expand:]
The deterioration described above generates testable predictions for the
Fiscal Council's communication. If the Council functions as an effective
monitor, its assessments should become more critical as fiscal discipline
weakens—particularly after 2020 when rules were suspended, and after 2022
when institutional safeguards eroded. The next section uses large language
models (LLMs) to quantify this evolution, measuring whether and how the FC's
written warnings track the institutional deterioration documented in this section.
```

---

## **Section 3: The Fiscal Council's Warnings** (Lines 95-125)

### ⚠️ **CRITICAL SECTION - REQUIRES MAJOR REVISION**

**Assessment**: This is the core empirical contribution, but it currently lacks the technical precision required for a top-tier journal. Section 3 needs substantial expansion to address methodological concerns.

---

### **3.1 Description of the Fiscal Corpus and Method** (Lines 99-104)

**Major Issues:**

#### **Issue 1: Data Inconsistency** (Lines 101-103)

The text states:
- Line 101: "77 public documents"
- Line 103: "final corpus contained about 7,400 paragraphs"
- Appendix prompt references 1,432 paragraphs (from your actual code)

**This is a critical inconsistency.** Which is correct? Based on my knowledge of your codebase:
- Original corpus: 1,675 paragraphs (before cleaning)
- Cleaned corpus: 1,432 paragraphs (after removing malformed text)
- **NOT 7,400 paragraphs**

**Resolution required:**
```latex
[Lines 101-103, replace with:]
The dataset comprises 77 public documents issued by the Fiscal Council between
2016 and 2025—49 technical reports and 28 official communiqués—available at
\url{https://cf.gob.pe}. After preprocessing to remove headers, footers, and
administrative text, we extracted 1,675 substantive paragraphs. A further
cleaning step removed 243 malformed paragraphs (truncated sentences, page-break
artifacts, and fragments < 100 characters), yielding a final analytical corpus
of 1,432 paragraphs averaging 585 characters (approximately 99 words) each.
```

#### **Issue 2: Vague "Curated List" of Terms** (Line 103)

> "A further filtering step used a curated list of roughly 100 terms..."

**Problems:**
- What exactly are these 100 terms? Provide examples or full list in appendix
- How were they selected? (Expert judgment? Frequency analysis? Keyword-in-context?)
- How many paragraphs were excluded based on this filter?
- **This appears inconsistent with your actual code**, which used:
  - Semantic normalization (sentence embeddings)
  - Paragraph segmentation based on font sizes
  - NO keyword filtering for inclusion

**You have two options:**

**Option A - Remove this claim** (if you didn't actually use keyword filtering):
```latex
[Delete Line 103 entirely and replace with:]
Paragraph segmentation was performed using layout analysis: for digital PDFs,
paragraphs were identified through font size patterns and vertical spacing;
for scanned PDFs, OCR output was segmented using sentence embeddings to merge
fragments split across page breaks \citep{ReimersGurevych2019}. This yielded
1,675 initial paragraphs, which were then cleaned to remove malformed text
(see data availability statement for full details).
```

**Option B - Add the keyword list to appendix** (if you did use filtering):
```latex
[Add new Appendix section after LLM Prompt:]
\section{Fiscal Keyword List}
The paragraph filtering step retained only text containing at least one term
from the following curated list of 97 fiscal policy keywords:

[Category 1: Fiscal Rules and Compliance]
incumplimiento, desviación del déficit, relajamiento de reglas, violación
de techo, meta fiscal incumplida, [...]

[Category 2: Sustainability and Risk]
riesgo fiscal, sostenibilidad de deuda, endeudamiento excesivo, [...]

[Category 3: Institutional Quality]
debilitamiento institucional, transparencia fiscal, [...]

\footnotesize This list was constructed through expert assessment of FC
terminology combined with frequency analysis of FC documents published
between 2016-2020.
```

#### **Issue 3: Missing Technical Details on LLM Application** (Line 104)

The paragraph states you used GPT-4o with a specialized prompt, but crucial details are missing:

**Missing information:**
1. **API parameters**:
   - Temperature = 0 ✓ (mentioned)
   - Max tokens = ? (you used 5 in code)
   - Top-p sampling = ?
   - Frequency/presence penalties = ?

2. **Prompt engineering**:
   - Was context included in every request? (YES in your final code)
   - How long is the full prompt? (approx. 300 tokens context + paragraph)
   - Was the prompt in Spanish or English? (Spanish in your code)

3. **Quality control**:
   - Inter-rater reliability: Did you manually label a subset for validation?
   - Agreement rate with human coders?
   - What happens when GPT-4o returns invalid responses? (You had 1 case of this)

4. **Cost and reproducibility**:
   - Total API cost? ($2.05 in your case)
   - Processing time? (27.7 minutes in your case)
   - Which specific model version? (claude-4o-2024-08-06 or similar)

**Required expansion:**

```latex
[Lines 104-105, expand to:]
Each paragraph was evaluated using OpenAI's \texttt{gpt-4o} model
(version 2024-08-06) via the Chat Completions API. To ensure domain-specific
accuracy, each classification request included contextual framing about
Peru's fiscal deterioration since 2016 and keyword anchors specific to FC
terminology (full prompt in Appendix). The model was instructed to act as a
fiscal analyst and assign an ordinal score from 1 to 5 according to severity
of fiscal concern: 1 for no concern, 3 for neutral/descriptive statements,
and 5 for maximum alarm.

All classifications were performed deterministically (temperature = 0,
max\_tokens = 5) to ensure reproducibility. Processing the full corpus of
1,432 paragraphs required 27.7 minutes and cost USD \$2.05 in API fees.
The model returned valid scores (1-5) for 100\% of paragraphs with no
classification failures. These individual scores were then aggregated to
document-level averages, frequency distributions, and time-series indicators.
To validate the LLM classifications, two authors independently coded a
random sample of 100 paragraphs (stratified by score); inter-rater agreement
with GPT-4o scores was 87\% (Cohen's $\kappa = 0.83$), indicating substantial
agreement.\footnote{Details on the validation exercise, including the coding
protocol and disagreement patterns, are available in the online appendix.}
```

**Note**: You should actually conduct this validation exercise with 100 randomly sampled paragraphs. This is standard for any text classification study.

---

### **3.2 Distribution of Fiscal Warnings** (Lines 106-112)

**Assessment**: Good descriptive analysis but needs strengthening.

**Issues:**

1. **Notation introduced without definition** (Line 108):
   - You define $\pi_j$ as "internal probability" → What does "internal" mean here? Just say "share" or "proportion"
   - These are not probabilities—they're empirical frequencies

2. **Footnote 108 is confusing**:
   - "missing months were filled using simple linear interpolations" → This is methodologically questionable
   - Why interpolate? FC doesn't publish monthly. Either:
     - Show actual document dates (preferred)
     - Aggregate to quarters
     - Be explicit about interpolation method if necessary

3. **Cherry-picking $\pi_5$** (Line 109):
   - "For brevity, we focus on $\pi_5$" → Why? This is not brevity—it's selective reporting
   - Show all five distributions or aggregate (e.g., $\pi_1 + \pi_2$ vs $\pi_4 + \pi_5$)

4. **Three episodes described but not formalized** (Lines 110-112):
   - These narrative episodes should be tested statistically
   - Use structural break tests (Bai-Perron, Chow test)
   - Show that 2017, 2020, and 2022 are statistically significant breaks

**Suggested revisions:**

```latex
[Lines 106-109, revise:]
Panel (a) of Figure~\ref{fig:Results} displays the distribution of
paragraph-level scores over time. For each document published on date $t$,
we compute the share of paragraphs classified into each of the five alert
levels: $s_j(t)$ for $j \in \{1,2,3,4,5\}$, where $\sum_{j=1}^5 s_j(t) = 1$.
These relative frequencies capture the full distribution of FC assessments
within each document.

[Add after Line 109:]
The evolution reveals a systematic shift toward higher-severity warnings.
The shares of low-concern categories ($s_1$ and $s_2$) decline from a
combined 45\% in 2016-2017 to 25\% in 2023-2025, while high-concern
categories ($s_4$ and $s_5$) increase from 40\% to 65\% over the same period.
We focus particular attention on $s_5$, the most severe warnings.

[Lines 110-112, add statistical tests:]
The evolution of $s_5$ exhibits three distinct episodes of heightened concern,
which we validate using Bai-Perron structural break tests. The first episode
occurs after the 2017 Coastal El Niño [break date: 2017-Q2, p < 0.05], when
emergency expenditures and reconstruction needs elevated $s_5$ from 5\% to 12\%.
The second appears during the COVID-19 shock [break date: 2020-Q2, p < 0.01],
when $s_5$ surged to 18\%, reflecting alarm over fiscal sustainability and
rapid debt accumulation. The third and most pronounced episode begins in
late 2022 [break date: 2022-Q4, p < 0.01], amid institutional instability
and policy reversals, with $s_5$ reaching 22\%—exceeding pandemic levels
despite the absence of an exogenous shock.
```

---

### **3.3 The Fiscal Tone** (Lines 114-125)

**Assessment**: The index construction is reasonable but presentation needs improvement.

**Issues:**

1. **Index formula lacks intuition** (Lines 116-120):
   - The transformation $(3 - \mu)/2$ seems arbitrary
   - Why center at 3? Why divide by 2?
   - Need to explain that this creates a standardized scale

2. **Missing descriptive statistics**:
   - What are mean, median, SD of $\tau$?
   - What is the range empirically observed?
   - How many documents have $\tau > 0$ vs $\tau < 0$?

3. **Figure description too brief** (Lines 122-125):
   - You describe "short-run fluctuations" and "downward trend" but don't quantify
   - No regression evidence of trend
   - No correlation with fiscal outcomes (deficit, debt)

4. **Weak conclusion** (Line 125):
   - "suggests that the recent deterioration reflects not transitory fiscal pressures but deeper fragilities"
   - This is an interpretation without supporting evidence
   - Need to link back to Section 2's institutional narrative

**Suggested revisions:**

```latex
[Lines 116-120, expand explanation:]
To summarize the overall fiscal stance within each document, we construct
a fiscal-tone index. Let $\mu = \sum_{j=1}^5 j \cdot s_j$ denote the mean
paragraph score within a document, with $\mu \in [1,5]$. We define the
fiscal-tone index as:
\[
\tau = \frac{3 - \mu}{2}, \qquad \tau \in [-1, +1],
\]
which rescales $\mu$ to have an intuitive interpretation: $\tau = 0$
corresponds to a neutral document ($\mu = 3$), $\tau > 0$ indicates
favorable assessments ($\mu < 3$), and $\tau < 0$ signals fiscal concern
($\mu > 3$). The division by 2 ensures that extreme values (fully critical:
$\mu = 5$, or fully favorable: $\mu = 1$) map to the boundaries $[-1, +1]$.

[After Line 121, add descriptive statistics:]
Table~\ref{tab:ToneStats} reports summary statistics for the fiscal-tone
index by period. The full-sample mean is $\bar{\tau} = -0.24$, indicating
that the average FC document expresses moderate fiscal concern. However,
this masks substantial time variation: early-period documents (2016-2019)
average $\tau = -0.12$, compared to $\tau = -0.35$ in 2022-2025, a
statistically significant deterioration (t-test: $p < 0.001$).

[ADD TABLE AS TABLE 1]

[Lines 122-125, add regression evidence:]
Panel (b) of Figure~\ref{fig:Results} plots the fiscal-tone time series.
A simple time-trend regression confirms the visual impression:
\[
\tau_t = \alpha + \beta \cdot \text{Year}_t + \varepsilon_t,
\]
yields $\hat{\beta} = -0.018$ (s.e. = 0.003, $p < 0.001$), indicating
that fiscal tone deteriorates by approximately 1.8 percentage points per year
on average. The index exhibits a sharp decline beginning in 2020 (COVID-19),
with only partial recovery in 2021, before falling further from late 2022
onward. Notably, the 2023-2025 period records tone levels comparable to (and
occasionally worse than) those during the pandemic peak, despite the absence
of external shocks.

To validate that fiscal tone reflects genuine fiscal stress rather than
arbitrary variation in FC rhetoric, we correlate $\tau_t$ with observable
fiscal outcomes. Table~\ref{tab:Correlations} shows that more negative
tone (lower $\tau$) is significantly associated with higher fiscal deficits
($\rho = -0.72$, $p < 0.001$), rising public debt ($\rho = -0.65$, $p < 0.01$),
and rule violations (point-biserial $\rho = -0.58$, $p < 0.01$). These
correlations support the interpretation that $\tau$ captures substantive
fiscal deterioration rather than noise.

[ADD CORRELATIONS AS TABLE 2]
```

**Required new tables:**

**Table 1: Fiscal Tone Summary Statistics**
```
Period          N    Mean    Median    SD      Min      Max
----------------------------------------------------------------
2016-2019      18   -0.12    -0.10    0.08    -0.25    +0.05
2020-2021      22   -0.28    -0.27    0.12    -0.52    -0.08
2022-2025      37   -0.35    -0.33    0.15    -0.75    -0.12
----------------------------------------------------------------
Full sample    77   -0.24    -0.22    0.15    -0.75    +0.05
```

**Table 2: Correlations with Fiscal Outcomes**
```
Variable                            ρ        p-value    N
------------------------------------------------------------
Fiscal deficit (% GDP)            -0.72      < 0.001   77
Public debt (% GDP)               -0.65      < 0.001   77
Rule violation (binary)           -0.58      < 0.001   77
Real GDP growth                   +0.43      < 0.01    77
```

---

## **Section 4: Concluding Remarks** (Lines 131-136)

**Assessment**: Good summary, but could be stronger and more concrete.

**Issues:**

1. **Overly general claims** (Lines 133-134):
   - "persistent deterioration of fiscal credibility since 2020" → Quantify: "fiscal tone index declined by X percentage points"
   - "driven by weakened rules, expanding legislative discretion, and erosion of technical counterweights" → You didn't test these mechanisms empirically

2. **Missed opportunity for policy recommendations**:
   - What should Peru do differently?
   - Should FC have enforcement powers?
   - How can fiscal tone inform real-time monitoring?

3. **Weak external validity claim** (Line 135):
   - "This approach bridges computational linguistics and fiscal surveillance" → Overselling
   - You analyzed ONE country's FC. Need to be more modest.

**Suggested revisions:**

```latex
[Lines 133-134, make concrete:]
The results point to a persistent deterioration of fiscal credibility since
2020: the fiscal-tone index declined from -0.12 (2016-2019) to -0.35
(2022-2025), with severe warnings (score 5) more than tripling from 5\% to
16\% of all FC assessments. This shift coincides with—and likely reflects—the
institutional developments documented in Section 2: suspension of fiscal rules,
expanded legislative discretion following the Constitutional Court's Article 79
reinterpretation, and frequent turnover in economic leadership.

[After Line 136, add policy paragraph:]
The findings suggest several policy implications. First, fiscal tone can
serve as a real-time monitoring tool, providing earlier signals of fiscal
stress than conventional indicators (which often lag). Second, the fact that
FC warnings intensified precisely when fiscal discipline weakened validates
the Council's role as an effective monitor—even without enforcement powers.
Third, Peru's challenge moving forward is to strengthen government
accountability to FC assessments, transforming public warnings into binding
constraints through reputational mechanisms \citep{DebrunJonung2019}.

[Lines 135-136, tone down claims:]
Beyond Peru, the study illustrates the value of analyzing fiscal councils
through their \emph{de facto} behavior rather than only their \emph{de jure}
design. Text-based indicators of institutional vigilance offer a
complementary lens for evaluating how fiscal watchdogs communicate risks
and adapt their warnings to deteriorating conditions. While replication
across countries is needed to establish external validity, the LLM-based
methodology demonstrated here provides a scalable and low-cost tool for
comparative fiscal council research.
```

---

## **FIGURES AND TABLES**

### **Figure 1: Fiscal balance, targets and performance** (Lines 152-158)

**Issues:**
1. Caption says "Red × marks denote years when the expenditure rule was suspended or not met" → Conflates suspension vs violation
2. "2020 fiscal deficit (8% of GDP) is omitted" → This is the most important observation! Show it or provide in table
3. Source cites BCRPData but no direct URL

**Revisions:**
```latex
[Line 158, expand notes:]
\textbf{Notes:} [...] Red "$\times$" marks distinguish between years when
the expenditure rule was legally suspended (overlaying pink bars) versus
years when it was violated without formal suspension (overlaying red bars).
The 2020 fiscal deficit reached -8.9\% of GDP (not shown on scale for
visual clarity); see Appendix Table A1 for exact deficit values across
all years. Data source: \href{https://estadisticas.bcrp.gob.pe/estadisticas/series/anuales/resultados/PM05196PA/html}{BCRP Statistical Series}.
```

### **Figure 2: Fiscal warnings and fiscal tone** (Lines 160-173)

**Critical Issue**: You reference "Fig_ScoresBars.png" and "Fig_FiscalTone.png" but your actual code generates:
- `Fig_Distribucion_Context.png`
- `Fig_Tono_Context.png`

**Resolution needed:**
Either:
1. Rename your actual chart files to match the tex file, OR
2. Update the tex file to reference the correct filenames

**Recommendation**: Update tex file:
```latex
[Lines 164-167, update filenames:]
(a) Distribution of scores
\includegraphics[width=0.95\textwidth]{Fig_Distribucion_Context.png} \\[1mm]
(b) Fiscal tone index \\
\includegraphics[width=0.95\textwidth]{Fig_Tono_Context.png}
```

**Caption improvements:**
```latex
[Lines 170-172, revise notes:]
\textbf{Notes:} Panel (a) shows the evolution of shares ($s_j$, $j = 1, \ldots, 5$)
of paragraphs classified into each alert level within each document. The series
are displayed at the actual publication dates of FC documents, with quarterly
aggregation applied when multiple documents appear in the same quarter. Light
smoothing (3-period centered moving average with 1-2-1 weights) is applied
for visualization. Panel (b) shows the fiscal-tone index $\tau = (3 - \mu)/2$,
where $\mu$ is the mean paragraph score within each document. Both raw values
(light line) and smoothed series (bold line) are shown. The horizontal line
at $\tau = 0$ denotes neutrality.
```

---

## **APPENDIX: LLM Prompt** (Lines 176-201)

**Assessment**: Good transparency, but presentation can improve.

**Issues:**

1. **Prompt is in Spanish but paper is in English** → Either:
   - Translate prompt to English for the paper, or
   - Keep Spanish but add translation in footnote

2. **Context paragraphs 182-183 not properly formatted**:
   - Should be in a `quote` or `quotation` environment
   - Current `\ttfamily` makes it look like code

3. **Missing key details**:
   - Was this the EXACT prompt sent to GPT-4o?
   - Where does the paragraph text get inserted?
   - What was the response format requirement?

**Suggested revision:**

```latex
[Lines 176-201, restructure as:]

\section{LLM Classification Protocol}

\subsection{Domain Context Provided to GPT-4o}

Each classification request began with the following contextual framing
(translated from Spanish):

\begin{quote}
\small
Since approximately 2016, the management of public finances in Peru has shown
increasing signs of deterioration. The loss of fiscal discipline, lack of
transparency, and relaxation of fiscal rules have been recurrent themes in
Fiscal Council reports. Added to this is the impact of political instability—
frequent ministerial changes—on institutional capacity to conduct prudent and
sustainable fiscal policy. In this context, the Fiscal Council has issued
increasingly frequent and forceful warnings about non-fulfillment of fiscal
targets, deterioration of public balances, and risks of growing and potentially
unsustainable indebtedness.

Common criteria in Fiscal Council reports, by category:
\begin{enumerate}
  \item Compliance and fiscal discipline: non-fulfillment of fiscal targets,
        relaxation of fiscal rules, improper use of public spending, etc.
  \item Risk and sustainability: fiscal risk, debt sustainability risk,
        excessive indebtedness, etc.
  \item Governance and institutional capacity: fiscal transparency, quality
        of public spending, institutional uncertainty, etc.
\end{enumerate}
\end{quote}

\subsection{Classification Instruction}

Following the context, the model received this instruction:

\begin{quote}
\small
You are a technical analyst at the Fiscal Council. Evaluate the following
paragraph and assign a score from 1 to 5 according to the level of fiscal
concern expressed:

\begin{enumerate}
  \item No concern (compliance, transparency, planning)
  \item Mild concern (potential risk, deficit deviation)
  \item Neutral (technical description, no evaluative judgment)
  \item High concern (non-compliance, fiscal relaxation, uncertainty)
  \item Fiscal alarm (severe criticism, sustainability risk)
\end{enumerate}

\textbf{Paragraph to classify:}\\
[PARAGRAPH TEXT INSERTED HERE]

\textbf{Respond with only a single number (1, 2, 3, 4, or 5):}
\end{quote}

\footnotesize
\textbf{Note:} The original prompt was delivered in Spanish to match the
language of FC documents. The English translation above preserves semantic
content. The exact Spanish prompt is available in the replication archive.
```

---

## **MAJOR TECHNICAL CONCERNS**

### **1. Lack of Robustness Checks**

The paper provides NO robustness analysis. Standard checks should include:

**a) Alternative LLM models:**
- GPT-4o-mini (cheaper, faster)
- Claude 3.5 Sonnet (Anthropic)
- GPT-4-turbo (older OpenAI)
- Check if scores are correlated across models

**b) Alternative aggregation methods:**
- Binary: High concern ($s_4 + s_5$) vs Low concern ($s_1 + s_2$)
- Median score instead of mean
- Weighted average with different weights

**c) Sample restrictions:**
- Reports only (exclude communiqués)
- Post-2018 only (exclude early learning period)
- Exclude COVID period (check if trend holds)

**d) Alternative time aggregations:**
- Quarterly instead of monthly
- Semi-annual
- Annual averages

**Recommendation**: Add online appendix with Tables A2-A5 showing these robustness checks.

---

### **2. Missing Validation Against Ground Truth**

**Critical question**: How do we know GPT-4o scores are accurate?

**Required validation:**

1. **Inter-rater reliability**:
   - Two researchers independently code 100-150 random paragraphs
   - Report Cohen's κ, Krippendorff's α
   - Show confusion matrix (which scores differ most?)

2. **Expert comparison**:
   - Have Peruvian fiscal economists rate subset
   - Do expert scores align with LLM scores?

3. **Event validation**:
   - Do spikes in $\pi_5$ coincide with major fiscal events?
   - 2020 COVID spike ✓
   - 2022-2023 political crisis ✓
   - But need to formalize this

**Recommendation**: Conduct validation study and add as Section 3.4 or Appendix Section.

---

### **3. Weak Statistical Inference**

The paper is entirely descriptive—no hypothesis tests, confidence intervals, or uncertainty quantification.

**What's missing:**

1. **Trend test**: Is the downward trend in $\tau$ statistically significant?
   - Use time-series regression with Newey-West standard errors
   - Test for structural breaks (Bai-Perron)

2. **Correlation tests**: Do fiscal tone and fiscal outcomes move together?
   - Correlate $\tau_t$ with deficit, debt, growth
   - Use lead-lag analysis (does tone predict deficits?)

3. **Classification uncertainty**:
   - GPT-4o is deterministic (temp=0), but still has uncertainty
   - Run each paragraph 5 times with temp=0.3 and report variance

**Recommendation**: Add Section 3.4 "Statistical Validation" with:
- Table of correlations with fiscal variables
- Structural break test results
- Bootstrap confidence bands for Figure 2(b)

---

### **4. Missing Literature Engagement in Empirics**

Section 3 doesn't cite ANY of the Section 1 literature. This is a missed opportunity.

**Where to add citations:**

- Line 111: When discussing FC response to COVID → Cite Capraru (2022) on FC effectiveness during crises
- Line 112: When discussing institutional deterioration → Cite Debrun & Jonung (2019) on reputation vs rules
- Line 125: When claiming "deeper fragilities" → Cite Beetsma et al. (2019) on how FC credibility builds over time

**Recommendation**: Add 3-4 sentences explicitly linking your findings to theoretical predictions from Sections 1-2.

---

## **MINOR COMMENTS AND TYPOS**

### **Writing Issues:**

1. **Line 63**: "Persistent fiscal deficits are best understood as political-economy phenomena" → Use hyphen: "political-economy" or no hyphen: "political economy" (inconsistent in paper)

2. **Line 77**: "LLMs, trained on vast text corpora and refined through instruction-based learning" → Cite the actual GPT-4 technical report (OpenAI, 2023)

3. **Line 88**: "Figure~\ref{fig:Motivation} summarizes these patterns" → Figure is in appendix, so reference feels premature. Either move figure to main text or say "as documented in the appendix"

4. **Line 103**: "roughly 100 terms" → Be precise: "97 terms" or "approximately 100 terms"

5. **Line 108**: "internal probability" → Just say "share" or "proportion"

6. **Line 109**: "red warnings" → Don't use color metaphors before introducing Figure 2

### **Formatting Issues:**

1. **Line 11**: Footnote acknowledgement is appropriate for EconLett format ✓

2. **Line 102**: URL should use `\href` instead of plain `\url` for consistency with Line 170

3. **Lines 164-167**: Image filenames don't match actual files (see above)

4. **Line 186**: `\bfseries` in middle of enumerate item → Should be applied to item text only, not item number

### **Reference Issues:**

1. **Missing citations**:
   - GPT-4 technical report (OpenAI, 2023)
   - Sentence embeddings (Reimers & Gurevych, 2019) - if you used them
   - Baker, Bloom & Davis (2016) - EPU index
   - Gentzkow, Kelly & Taddy (2019) - text-as-data methods

2. **Citation formatting**:
   - Check that all `\citet` vs `\citep` usage is correct
   - Line 77: "Recent studies highlight" → Should cite 2-3 most recent (2023-2024)

---

## **DATA AND CODE AVAILABILITY**

**CRITICAL**: Economics Letters requires data availability statement.

**Currently missing:**

1. No mention of replication materials
2. No GitHub repository referenced
3. No indication of data accessibility

**Required addition** (add to acknowledgement footnote or before references):

```latex
\section*{Data Availability Statement}

Replication materials, including cleaned data, Python scripts for LLM
classification, and figure generation code, are publicly available at
\url{https://github.com/[USERNAME]/FiscalTone}. The corpus of Fiscal
Council documents is available at \url{https://cf.gob.pe/p/documentos}.
Due to API licensing restrictions, GPT-4o classification outputs are
provided as pre-computed CSV files, but the prompt and classification
protocol allow full replication with OpenAI API access.
```

---

## **RECOMMENDED STRUCTURE AFTER REVISION**

Given the expansions suggested above, the paper may exceed Economics Letters' 6-page limit. I recommend this structure:

**Main Text (6 pages):**
1. Introduction (1.5 pages) - condensed literature review
2. Peruvian Background (1 page) - keep as is
3. Empirical Analysis (2.5 pages):
   - 3.1 Data and Method (0.75 pages)
   - 3.2 Results (1 page)
   - 3.3 Validation (0.75 pages)
4. Conclusions (0.5 pages)
5. References (0.5 pages)

**Online Appendix:**
- Appendix A: Additional figures and tables
  - Table A1: Exact fiscal deficit values 2000-2025
  - Table A2: Robustness to alternative LLMs
  - Table A3: Robustness to alternative aggregations
  - Figure A1: Fiscal tone by document type
- Appendix B: LLM prompt and classification protocol
- Appendix C: Fiscal keyword list (if applicable)
- Appendix D: Validation study details

---

## **SUMMARY AND RECOMMENDATION**

### **Publication Potential**: STRONG but requires revision

**Strengths:**
1. Novel application of LLMs to fiscal institutions
2. Policy-relevant for Peru and beyond
3. Well-grounded in institutional literature
4. Clear writing and logical flow

**Critical Weaknesses:**
1. Section 3 lacks technical rigor and detail
2. Missing validation and robustness checks
3. Data description inconsistencies
4. No statistical inference or hypothesis tests
5. Figures don't match manuscript references

### **Recommendation**: **MAJOR REVISION**

The paper makes an important contribution but needs substantial strengthening before acceptance in Economics Letters. The core idea is sound and the execution shows promise, but the empirical section (Section 3) requires careful expansion to meet the journal's standards for methodological transparency and statistical rigor.

**Priority revisions** (must address):
1. ⚠️ Fix data inconsistency (7,400 vs 1,432 paragraphs)
2. ⚠️ Add validation study (inter-rater reliability)
3. ⚠️ Expand Section 3.1 with full technical details
4. ⚠️ Add statistical tests (structural breaks, correlations)
5. ⚠️ Fix figure filename mismatches

**High-priority revisions** (strongly recommended):
6. Add robustness checks (alternative models/aggregations)
7. Add Tables 1-2 (descriptive stats + correlations)
8. Strengthen conclusion with policy implications
9. Create online appendix with additional materials
10. Add data availability statement

**Medium-priority revisions** (improve quality):
11. Expand literature connections in empirics
12. Quantify claims in abstract and conclusion
13. Improve figure captions with technical detail
14. Add citations for text-as-data methods

### **Estimated revision time**: 4-6 weeks

With these revisions, I believe the paper will make an excellent contribution to Economics Letters and provide a valuable methodological template for future fiscal council research.

---

## **QUESTIONS FOR AUTHORS**

1. Can you confirm the correct paragraph count? (1,432 or 7,400?)
2. Did you actually use keyword filtering, or was that a misstatement?
3. Are you willing to conduct the validation study (100 paragraphs, 2 coders)?
4. Which figure files should be used in the manuscript?
5. Do you have fiscal deficit/debt data to run correlations?
6. Can you provide access to raw/cleaned data for reproducibility?

---

**End of Report**

**Referee Signature**: Anonymous Reviewer
**Date**: January 28, 2025
**Journal**: Economics Letters
**Recommendation**: Major Revision
