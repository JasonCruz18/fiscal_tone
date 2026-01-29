# Data Availability Statement

## Dataset Repository

The Fiscal Tone Dataset is openly available on Zenodo:

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.XXXXXXX-blue)](https://doi.org/10.5281/zenodo.XXXXXXX)

> **Note**: The DOI badge above will be updated once the dataset is published on Zenodo.

## Dataset Contents

The published dataset includes:

| File | Description | Format |
|------|-------------|--------|
| `fiscal_tone_paragraphs.csv` | Paragraph-level scores with text and metadata | CSV |
| `fiscal_tone_documents.csv` | Document-level aggregated scores | CSV |
| `fiscal_tone_index.csv` | Time series of Fiscal Tone Index | CSV |
| `cf_metadata.csv` | Complete metadata for all documents | CSV |
| `codebook.pdf` | Variable definitions and methodology | PDF |

## Data Access

### Open Access

The dataset is published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) license, allowing:
- **Share**: Copy and redistribute in any medium or format
- **Adapt**: Remix, transform, and build upon the material
- **Commercial use**: For any purpose, including commercial

### Attribution Requirement

When using this dataset, please cite both the data paper and the Zenodo repository:

```bibtex
@article{cruz2025fiscaltone_data,
  author = {Cruz, Jason},
  title = {Fiscal Tone Dataset: Sentiment Analysis of Peru's Fiscal Council Communications},
  journal = {Data in Brief},
  year = {2025}
}

@dataset{cruz2025fiscaltone_zenodo,
  author = {Cruz, Jason},
  title = {Fiscal Tone Dataset for Peru (2016-2025)},
  year = {2025},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.XXXXXXX}
}
```

## Software Repository

The pipeline software that generates this dataset is available on GitHub:

- **Repository**: [github.com/JasonCruz18/FiscalTone](https://github.com/JasonCruz18/FiscalTone)
- **License**: [MIT License](../LICENSE)
- **Documentation**: See repository README and docs/

The software is independently citable and linked to the dataset via GitHub-Zenodo integration.

## Data Collection Period

- **Start Date**: 2016 (establishment of Peru's Fiscal Council)
- **End Date**: Ongoing (updated periodically)
- **Documents**: 75+ Informes and Comunicados

## Reproducibility

To reproduce the dataset from source:

1. Clone the repository
2. Install dependencies (see [INSTALLATION.md](INSTALLATION.md))
3. Run the complete pipeline:
   ```bash
   python scripts/run_pipeline.py --all
   ```

All intermediate outputs are preserved for verification.

## Contact

For questions about the dataset:
- **Author**: Jason Cruz
- **Email**: jj.cruza@up.edu.pe
- **Institution**: Universidad del Pacífico, Lima, Peru

## Related Publications

- Data paper: *Data in Brief* (forthcoming)
- Research paper: *(if applicable)*

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-XX-XX | Initial release |

---

*This data availability statement follows [FAIR principles](https://www.go-fair.org/fair-principles/) for scientific data management.*
