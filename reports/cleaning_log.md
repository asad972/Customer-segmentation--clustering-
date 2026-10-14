# Data cleaning log

_Generated automatically by `src/clean.py`; do not edit by hand._

- Raw rows: **1,067,371**
- Clean rows: **776,579** (72.8% of raw)
- Customers: **5,852**
- Invoices: **36,594**
- Products: **4,620**
- Period: **2009-12-01** to **2011-12-09**
- Revenue (clean): **£17,068,583**

## Steps

| # | Step | Rows before | Rows removed | Rows after | Why |
|---|------|------------:|-------------:|-----------:|-----|
| 1 | Missing Customer ID | 1,067,371 | 243,007 | 824,364 | Purchases cannot be attributed to a customer, so they cannot be segmented. |
| 2 | Exact duplicate rows | 824,364 | 26,479 | 797,885 | Identical lines (same invoice, product, quantity, price, time) are data-entry or export duplicates, including the overlap between the two Excel sheets. |
| 3 | Cancellation invoices (prefix 'C') | 797,885 | 18,390 | 779,495 | Returns/cancellations are not purchases; RFM should reflect what customers bought. |
| 4 | Non-positive quantity | 779,495 | 0 | 779,495 | Stock adjustments (damaged, lost, etc.) that are not customer purchases. |
| 5 | Zero or negative price | 779,495 | 70 | 779,425 | Free samples, internal adjustments and bad-debt write-offs carry no revenue. |
| 6 | Non-product stock codes | 779,425 | 2,846 | 776,579 | Postage, carriage, manual adjustments, discounts, bank charges and test codes are not products and would distort spend and product-variety features. |

## Notes

- Cancellations: 7,901 cancellation invoices from 2,572 customers, worth £1,084,813. They are excluded rather than netted against original orders because most originals cannot be matched one-to-one (many pre-date the dataset window).
- Non-product stock codes removed: `POST` (POSTAGE, 1,803 rows), `M` (Manual, 681 rows), `C2` (CARRIAGE, 248 rows), `ADJUST` (Adjustment by john on 26/01/2010 16, 32 rows), `BANK CHARGES` (Bank Charges, 31 rows), `PADS` (PADS TO MATCH ALL CUSHIONS, 17 rows), `DOT` (DOTCOM POSTAGE, 16 rows), `TEST001` (This is a test product., 9 rows), `D` (Discount, 5 rows), `ADJUST2` (Adjustment by Peter on Jun 25 2010, 3 rows), `TEST002` (This is a test product., 1 rows)

## Validation checks passed

- Raw file has the expected 8 columns and at least 1,000,000 rows
- No missing Customer IDs
- No cancellation invoices (prefix 'C') remain
- All quantities and prices are strictly positive
- No exact duplicate rows
- Only product stock codes remain
- All invoice dates fall within 2009-12-01 to 2011-12-31
- Revenue equals Quantity x Price for every row
- Each invoice belongs to exactly one customer
