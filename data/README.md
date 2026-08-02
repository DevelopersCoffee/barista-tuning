# Data

`data/raw/Zomato_Menu_Scraped.xlsx` is the local sample source data for menu question answering.

Workbook shape:

- Sheet: `Sheet1`
- Rows: `88,143`
- Columns: `URL`, `Restaurant_Name`, `Category`, `Item_Name`, `Price`

Raw and processed data files are ignored by git. Keep reproducible conversion or cleaning logic in `scripts/`.

The enterprise-knowledge training source is the generic governed catalog at
`examples/enterprise_knowledge/metadata_catalog.json`. Generate its processed SFT
splits reproducibly with:

```bash
slm generate-enterprise-knowledge-splits \
  examples/enterprise_knowledge/metadata_catalog.json
```

Do not add customer records, production payloads, credentials, or proprietary source
code to the catalog or generated training data.
