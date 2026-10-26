"""Canonical import contracts, not assumptions about unseen marketplace exports."""
from dataclasses import dataclass
import pandas as pd

BUS = ['GT/PRO','GT/DIY','OG/PRO','OG/DIY','MT/PRO','MT/DIY','AC/PRO','AC/DIY','HD']
@dataclass(frozen=True)
class Schema:
    title: str
    required: tuple
    optional: tuple
    numeric: tuple
    keys: tuple
    note: str

SCOPE = ('country','marketplace')
MONTH = SCOPE + ('period','currency')
RATES = ('gm_pct','gm_basis','return_rate','return_basis','cost_concession_pct','concession_basis')
SCHEMAS = {
 'financial_actuals': Schema('Monthly financial actuals', MONTH+('tns',), RATES+('orders','reported_aov'), ('tns','orders','reported_aov')+RATES, SCOPE+('period',), 'Rates are finance-approved percentages (0–100). Bases are approved weighting denominators. TNS and finance rates are never inferred from GMV.'),
 'forecasts': Schema('Targets & forecasts', SCOPE+('period_start','period_end','currency','scenario','tns'), RATES+('orders','visitors','buyers'), ('tns','orders','visitors','buyers')+RATES, SCOPE+('period_start','period_end','scenario'), 'Scenario: official, stretch or target. Upload monthly forecasts and separate full-year targets. Audience forecasts must cover the exact requested period.'),
 'marketplace': Schema('Marketplace sales', MONTH+('sales_basis','gmv'), ('orders','units','reported_aov'), ('gmv','orders','units','reported_aov'), SCOPE+('period','sales_basis'), 'Monthly shop aggregates only. Order-level exports need a reviewed adapter before import.'),
 'products': Schema('Product performance', MONTH+('sales_basis','listing_sku','product_name','revenue','units'), ('visitors','buyers','atc_units','gm_pct','gm_basis'), ('revenue','units','visitors','buyers','atc_units','gm_pct','gm_basis'), SCOPE+('period','sales_basis','listing_sku'), 'One row per sellable listing per month. Canonical SKU mapping is mandatory. Bundles keep their own identity.'),
 'traffic': Schema('Traffic & conversion', SCOPE+('sales_basis','period_start','period_end','visitors','buyers'), ('reported_cr_pct','reported_order_cr_pct','product_clicks'), ('visitors','buyers','reported_cr_pct','reported_order_cr_pct','product_clicks'), SCOPE+('sales_basis','period_start','period_end'), 'Audience counts must be unique within this exact store and interval. YTD requires a deduplicated YTD export; monthly uniques are never summed.'),
 'ads': Schema('Advertising performance', MONTH+('spend','ads_gmv','attribution_model'), ('ad_orders',), ('spend','ads_gmv','ad_orders'), SCOPE+('period','attribution_model'), 'Ads GMV is attributed revenue, never total shop GMV. Use compatible attribution models for aggregation.'),
 'marketplace_daily': Schema('Daily marketplace performance', SCOPE+('date','currency','sales_basis','gmv','orders','visitors','buyers'), ('units','reported_cr_pct','reported_order_cr_pct'), ('gmv','orders','visitors','buyers','units','reported_cr_pct','reported_order_cr_pct'), SCOPE+('date','sales_basis'), 'Daily-grain only, separate from authoritative monthly summaries. Daily audiences are not added into monthly or YTD unique counts.'),
 'contributions': Schema('Source product contribution excerpts', MONTH+('sales_basis','channel','listing_sku','product_name','revenue','units'), ('source_orders','buyers','product_clicks','unique_product_clicks','reported_order_cr_pct'), ('revenue','units','source_orders','buyers','product_clicks','unique_product_clicks','reported_order_cr_pct'), SCOPE+('period','sales_basis','channel','listing_sku'), 'Incomplete channel excerpts from Shopee shop statistics. These are not full product sales, SKU visitors or an approved Bosch material mapping; never summed across channels into SKU totals.'),
 'listing_products': Schema('Marketplace product listing performance', MONTH+('sales_basis','listing_sku','product_name','revenue','units'), ('visitors','buyers','atc_units','orders','reported_cr_pct','source_material','period_source'), ('revenue','units','visitors','buyers','atc_units','orders','reported_cr_pct'), SCOPE+('period','sales_basis','listing_sku'), 'Authoritative product-total rows only. Listing IDs are source identities, not approved Bosch material mappings. Never add variant rows to these totals.'),
 'listing_variants': Schema('Marketplace sellable variant detail', MONTH+('sales_basis','listing_sku','variant_id','product_name','revenue','units'), ('variant_name','seller_sku','visitors','buyers','atc_units','orders','period_source'), ('revenue','units','visitors','buyers','atc_units','orders'), SCOPE+('period','sales_basis','listing_sku','variant_id'), 'Variant rows only, kept separate from product totals. Product-level visitors are never allocated to variants. Seller SKU is source-reported and is not automatically an approved cross-market canonical mapping.'),
 'kpi_benchmarks': Schema('BRM KPI benchmarks', SCOPE+('period_start','period_end','scenario'), ('gm_pct','visitors','buyers','orders','return_rate'), ('gm_pct','visitors','buyers','orders','return_rate'), SCOPE+('period_start','period_end','scenario'), 'Explicit source forecast/target benchmarks. Fractional modeled counts are retained; not actual counts.'),
 'financial_rates': Schema('Reported monthly finance rates', SCOPE+('period','gm_pct','source_cell'), ('gm_basis',), ('gm_pct','gm_basis'), SCOPE+('period',), '2026 monthly source-reported GM only. No weighting denominator is assumed; YTD needs an approved basis.'),
 'brm_tracking': Schema('BRM Monthly Tracking reference', MONTH+('sales_basis','gmv','visitors','buyers','orders'), ('units','returned_amount','cancelled_amount','reported_cr_pct'), ('gmv','visitors','buyers','orders','units','returned_amount','cancelled_amount','reported_cr_pct'), SCOPE+('period','sales_basis'), 'Reference-only manual tracking. Raw 2026 exports take precedence; unknown historical Shopee order status is not relabeled Confirmed.'),
 'brm_review': Schema('BRM source checks', ('tab','cell','metric','detail'), ('period','value'), ('value',), ('tab','cell'), 'Workbook provenance and review findings; not authoritative KPI input.'),
 'sku_master': Schema('Bosch SKU master', SCOPE+('listing_sku','canonical_sku','product_name','business_unit','product_group','is_bundle'), (), (), SCOPE+('listing_sku',), 'Approved mapping only. is_bundle is true/false. Do not allocate bundles to components without an approved methodology.'),
 'fx': Schema('FX reference rates', ('period','from_currency','to_currency','rate','methodology'), (), ('rate',), ('period','from_currency','to_currency','methodology'), 'Rate multiplies source currency to reporting currency. No implicit inverse, cross-rate or carry-forward.'),
}
ALIASES = {'month':'period','material number':'listing_sku','material no.':'listing_sku','sku':'listing_sku','sales':'revenue','units sold':'units','unique visitors':'visitors','add to cart units':'atc_units','ad spend':'spend','roas gmv':'ads_gmv','business unit':'business_unit','product group':'product_group'}

def suggest_mapping(columns, category):
    fields = SCHEMAS[category].required + SCHEMAS[category].optional
    found = {}
    for col in columns:
        name = str(col).strip().lower()
        canonical = ALIASES.get(name, name.replace(' ','_'))
        if canonical in fields and canonical not in found:
            found[canonical] = col
    return found

def recognize(columns):
    names = {str(c).strip().lower().replace(' ','_') for c in columns}
    if {'from_currency','to_currency','rate'} <= names: return 'fx'
    if 'canonical_sku' in names: return 'sku_master'
    if 'attribution_model' in names or 'ads_gmv' in names: return 'ads'
    if 'scenario' in names: return 'forecasts'
    if 'tns' in names: return 'financial_actuals'
    if 'listing_sku' in names or 'product_name' in names: return 'products'
    if 'visitors' in names and 'period_start' in names: return 'traffic'
    return 'marketplace'

def template(category):
    s = SCHEMAS[category]
    return pd.DataFrame(columns=s.required+s.optional).to_csv(index=False)
