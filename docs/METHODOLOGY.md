# Research Methodology

## Overview

FiscalTone constructs a Fiscal Tone Index by analyzing official communications from Peru's Fiscal Council (Consejo Fiscal) using LLM-based text classification.

## Data Collection

### Source

Peru's Fiscal Council publishes two types of documents:
- **Informes**: Formal reports on fiscal policy matters
- **Comunicados**: Press releases and public communications

Source URLs:
- https://cf.gob.pe/p/informes/
- https://cf.gob.pe/p/comunicados/

### Collection Period

- **Start**: 2016 (establishment of Fiscal Council)
- **End**: Present (ongoing collection)
- **Total Documents**: 75+ reports

### Exclusions

The following are excluded from analysis:
- Annual reports (statistical summaries, not opinions)
- Presentations (PowerPoint files)
- Administrative documents

## Text Processing

### PDF Classification

PDFs are classified as:
- **Editable**: Contain extractable text (digital PDFs)
- **Scanned**: Image-based requiring OCR

### Text Extraction

For editable PDFs:
1. Extract text using PyMuPDF
2. Filter by font size (11.0-11.9pt) to capture body text
3. Exclude headers, footers, and titles
4. Detect paragraph boundaries via vertical spacing

For scanned PDFs:
1. Convert pages to images (300 DPI)
2. Apply OCR via Tesseract
3. Use region-based cropping to exclude margins

### Content Filtering

The extraction focuses on "Opinión del CF" sections:
1. Search for keyword "Opinión del Consejo Fiscal" from page 2+
2. Truncate at "Anexo" sections
3. Remove letter pages and cover pages

## Text Cleaning Pipeline

Eight-stage cleaning process:

| Stage | Purpose |
|-------|---------|
| 0 | Preliminary normalization (OCR artifacts) |
| 1 | Keyword filtering (locate opinion section) |
| 2 | False paragraph break removal |
| 3 | Header/title removal |
| 4 | Annex truncation |
| 5 | Letter page removal |
| 6 | Noise reduction |
| 7 | Final normalization |

## LLM Classification

### Model

- **Provider**: OpenAI
- **Model**: GPT-4o
- **Temperature**: 0 (deterministic)

### Prompt Design

The prompt includes:
1. **Domain Context**: Background on Peruvian fiscal policy deterioration since 2016
2. **Classification Criteria**: Detailed descriptions for each score level
3. **Examples**: Implicit through category keywords

### Scoring Scale

| Score | Label | Description | Keywords |
|-------|-------|-------------|----------|
| 1 | No concern | Fiscal consolidation, compliance | disciplina, transparencia, cumplimiento |
| 2 | Slight concern | Potential risks | riesgo potencial, dependencia |
| 3 | Neutral | Technical description | descripción, análisis técnico |
| 4 | High concern | Non-compliance, uncertainty | incumplimiento, relajamiento, incertidumbre |
| 5 | Alarm | Severe criticism, debt risk | alarma, sostenibilidad, crítica severa |

### Domain Context

The prompt includes context about:
- Fiscal deterioration since 2016
- Loss of fiscal discipline
- Lack of transparency
- Political instability impact
- Recurring themes in CF communications

## Index Construction

### Paragraph-Level

Each paragraph receives:
- `fiscal_risk_score`: 1-5 integer
- `risk_index`: (3 - score) / 2, ranging from -1 to +1

### Document-Level Aggregation

Documents are aggregated by:
- `avg_risk_score`: Mean of paragraph scores
- `fiscal_tone_index`: (3 - avg_risk_score) / 2
- Score distribution: Count of paragraphs per score level

### Interpretation

| Fiscal Tone Index | Interpretation |
|-------------------|----------------|
| +1.0 | Highly positive (no fiscal concerns) |
| +0.5 | Moderately positive |
| 0.0 | Neutral |
| -0.5 | Moderately negative |
| -1.0 | Highly negative (fiscal alarm) |

## Quality Assurance

### Rate Limiting

- 50 requests per minute (respects API limits)
- Automatic retry with exponential backoff

### Validation

- Score must be in {1, 2, 3, 4, 5}
- Invalid responses trigger retry
- Manual review of edge cases

### Reproducibility

- Temperature = 0 for deterministic outputs
- All prompts and context are version-controlled
- Incremental backups during processing

## Limitations

1. **Model Bias**: LLM may have inherent biases in political/economic text
2. **Context Window**: Long documents may need chunking
3. **Spanish Language**: Model trained primarily on English
4. **Temporal Drift**: Model knowledge cutoff may affect recent events
5. **OCR Errors**: Scanned documents may have extraction errors

## References

- Peru Fiscal Council: https://cf.gob.pe/
- OpenAI GPT-4o: https://platform.openai.com/docs/models/gpt-4o
