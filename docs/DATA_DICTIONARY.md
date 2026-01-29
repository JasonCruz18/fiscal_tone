# Data Dictionary

## Metadata Files

### cf_metadata.json

PDF metadata from web scraping.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `date` | string | Publication date (ISO format) | "2020-03-15" |
| `year` | string | 4-digit year | "2020" |
| `month` | integer | Month number (1-12) | 3 |
| `page_url` | string | Detail page URL | "https://cf.gob.pe/p/..." |
| `pdf_url` | string | Direct PDF download URL | "https://cf.gob.pe/docs/..." |
| `pdf_filename` | string | Local filename | "Informe-001-2020-CF.pdf" |
| `pdf_type` | string | "editable" or "scanned" | "editable" |
| `doc_title` | string | Document title from webpage | "Informe CF N 001-2020" |
| `doc_type` | string | "Informe" or "Comunicado" | "Informe" |
| `doc_number` | integer | Document number (no leading zeros) | 1 |

### cf_extracted_text.json

Raw extracted text by page.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pdf_filename` | string | Source PDF filename | "Informe-001-2020-CF.pdf" |
| `page` | integer | Page number (1-indexed) | 3 |
| `text` | string | Extracted text content | "El CF considera..." |

### cf_cleaned_text.json

Cleaned and normalized text.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pdf_filename` | string | Source PDF filename | "Informe-001-2020-CF.pdf" |
| `page` | integer | Page number | 3 |
| `paragraph_num` | integer | Paragraph number within document | 5 |
| `text` | string | Cleaned paragraph text | "El CF considera..." |
| `date` | string | Publication date | "2020-03-15" |
| `year` | string | Year | "2020" |
| `month` | integer | Month | 3 |
| `doc_type` | string | Document type | "Informe" |
| `doc_number` | integer | Document number | 1 |
| `doc_title` | string | Document title | "Informe CF N 001-2020" |

## Output Files

### llm_output_paragraphs.json

Paragraph-level classification results.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pdf_filename` | string | Source PDF | "Informe-001-2020-CF.pdf" |
| `page` | integer | Page number | 3 |
| `paragraph_num` | integer | Paragraph number | 5 |
| `text` | string | Paragraph text | "El CF considera..." |
| `fiscal_risk_score` | integer | Risk score (1-5) | 4 |
| `risk_index` | float | (3 - score) / 2 | -0.5 |
| `date` | string | Publication date | "2020-03-15" |
| `year` | string | Year | "2020" |
| `month` | integer | Month | 3 |
| `doc_type` | string | Document type | "Informe" |
| `doc_number` | integer | Document number | 1 |
| `doc_title` | string | Document title | "Informe CF N 001-2020" |

### llm_output_documents.json

Document-level aggregated results.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `pdf_filename` | string | Source PDF | "Informe-001-2020-CF.pdf" |
| `date` | string | Publication date | "2020-03-15" |
| `avg_risk_score` | float | Mean paragraph score | 3.5 |
| `avg_risk_index` | float | Mean risk index | -0.25 |
| `fiscal_tone_index` | float | (3 - avg_score) / 2 | -0.25 |
| `n_paragraphs` | integer | Number of paragraphs | 12 |
| `doc_title` | string | Document title | "Informe CF N 001-2020" |
| `doc_type` | string | Document type | "Informe" |
| `doc_number` | integer | Document number | 1 |
| `year` | string | Year | "2020" |
| `month` | integer | Month | 3 |
| `score_1` | integer | Count of score=1 paragraphs | 1 |
| `score_2` | integer | Count of score=2 paragraphs | 2 |
| `score_3` | integer | Count of score=3 paragraphs | 4 |
| `score_4` | integer | Count of score=4 paragraphs | 4 |
| `score_5` | integer | Count of score=5 paragraphs | 1 |

## Score Definitions

### fiscal_risk_score (1-5)

| Score | Label | Criteria |
|-------|-------|----------|
| 1 | No concern | Fiscal consolidation, compliance, transparency |
| 2 | Slight concern | Potential risks, extraordinary revenue dependency |
| 3 | Neutral | Technical description, no value judgment |
| 4 | High concern | Non-compliance, fiscal loosening, uncertainty |
| 5 | Alarm | Severe criticism, debt sustainability risk |

### risk_index (-1 to +1)

Formula: `(3 - fiscal_risk_score) / 2`

| Score | Risk Index | Interpretation |
|-------|------------|----------------|
| 1 | +1.0 | Very positive |
| 2 | +0.5 | Positive |
| 3 | 0.0 | Neutral |
| 4 | -0.5 | Negative |
| 5 | -1.0 | Very negative |

### fiscal_tone_index (-1 to +1)

Document-level aggregation of risk_index.

Formula: `(3 - avg_risk_score) / 2`

## File Formats

### JSON Files

- Encoding: UTF-8
- Format: Pretty-printed with 2-space indentation
- Array of objects (one per record)

### CSV Files

- Encoding: UTF-8
- Delimiter: Comma
- Header row: Yes
- Quoting: As needed for text fields

## Directory Structure

```
data/
├── raw/
│   ├── editable/          # Editable PDFs
│   └── scanned/           # Scanned PDFs
├── input/                 # Preprocessed data
└── output/                # Final outputs
    ├── llm_output_paragraphs.json
    ├── llm_output_paragraphs.csv
    ├── llm_output_documents.json
    └── llm_output_documents.csv

metadata/
├── cf_metadata.json
├── cf_extracted_text.json
└── cf_cleaned_text.json
```
