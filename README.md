# Streamlit BRM Dashboard

Malaysia-only e-commerce reporting for Shopee and Lazada. Shopee reporting uses Confirmed Orders. Includes executive KPIs, financial forecasts, sales/traffic, product and variant analysis, conversion opportunities, advertising, and the five-tab BRM source review.

## Free Streamlit deployment

Go to https://share.streamlit.io/ and create an app:

| Setting | Value |
|---|---|
| Repository | `Waker12/Streamlit-BRM-Dashboard` |
| Branch | `main` |
| Main file | `app.py` |
| Python | `3.12` |

In **Advanced settings → Secrets**, set your own long random password:

```toml
BOSCH_BI_REQUIRE_AUTH = "1"
BOSCH_BI_PASSWORD = "REPLACE_WITH_YOUR_OWN_LONG_RANDOM_PASSWORD"
```

Keep the password in Streamlit's private secrets settings, never in GitHub or chat. Deploy and sign in at the generated `.streamlit.app` address. Authentication defaults to required; without a configured password the app stays locked. This is a shared owner-password gate, not individual roles, MFA or enterprise SSO.

No Render subscription is required. A fresh deployment contains synthetic demo data and an empty Uploaded data workspace. After signing in, use **Data workspace** to import reports. No source workbooks, reporting databases or private audit reports are bundled.

To load a prepared workspace, open **Data workspace → Transfer existing workspace**, upload the private ZIP package and click **Import workspace package**. All included datasets are validated and committed together; conflicting records require explicit replacement. Then select **Uploaded data** in the sidebar. Original source import history is retained in the audit trail.

Use **Prepare workspace backup → Download private workspace backup** after monthly updates. Packages contain confidential reporting data; keep them locally and never commit them to this public repository.

**Storage limitation:** Community Cloud local storage can reset on reboot or redeployment. Retain your original exports and workspace backups so you can restore them with one upload. Automatic persistent external storage is not implemented; permanent historical data storage is not promised.

## Local use

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Put the same private secrets in `.streamlit/secrets.toml`, which is ignored by Git. PowerShell activation: `.venv\Scripts\Activate.ps1`.

## Data controls

Inspected adapters support internal MY TNS, Shopee shop/product XLSX, Lazada shop/product XLS, and the five main performance-workbook tabs. Current-year raw exports take precedence over manual tracking. Historical Shopee order status is kept distinct until verified.

Product totals and variant rows remain separate. Seller SKU text is not automatically an approved canonical material or BU. Missing data differs from zero. Monthly unique audiences are not added into deduplicated YTD or cross-store counts. Financial rates require approved weighting bases. Advertising attribution scopes remain separate; wrong-year denominators are excluded. Bosch fixed reporting FX is EUR 1 = MYR 4.64. Templates contain headers only.

## Tests

```bash
python -m pytest -q
```

Tests use synthetic fixtures. Optional private-workbook checks run only when explicit local file/manifest environment variables are supplied. They are skipped on a clean checkout.
