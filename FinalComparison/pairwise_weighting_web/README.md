# Pairwise weighting website

Generate the browser dataset after updating the pairwise analysis:

```bash
python3 FinalComparison/export_pairwise_web_data.py
```

Serve the repository locally:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/FinalComparison/pairwise_weighting_web/`.

The five user weights are normalized automatically. The structural result uses
the five `*_struct` scores, while the total result uses the corresponding five
`*_total` scores.
