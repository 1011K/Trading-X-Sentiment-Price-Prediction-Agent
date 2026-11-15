# GitHub publication instructions

Target: `https://github.com/1011K/entiment-price-prediction`.

This target URL must **not** be represented as a published repository until it resolves and the files are verified. As of the 2026-11-15 check, the target returned 404 through the connected GitHub account.

1. Create a **blank** repository named `entiment-price-prediction` under owner `1011K`: https://github.com/new?name=entiment-price-prediction. Do not initialize a README, license, or .gitignore.
2. If using the included Git bundle, restore the repository history with `git clone entiment-price-prediction.bundle entiment-price-prediction`; enter the directory and then run:

```bash
git remote remove origin 2>/dev/null || true
git remote add origin https://github.com/1011K/entiment-price-prediction.git
git push -u origin main
```

Alternatively, unzip the source archive, initialize Git, commit and push the source. Do not upload any secrets or datasets.

After pushing, verify the GitHub web page contains README.md, src/, tests/, docs/, archive/ and .github/workflows/tests.yml, and that Actions tests pass.
