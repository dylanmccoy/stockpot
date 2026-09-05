# Which inventory-upkeep problem is actually real?

Type: grilling
Status: open
Blocked by: 03
Parent: ../map.md

## Question

Inventory accuracy is the load-bearing assumption under three separate
features — availability checks, grocery netting, and cook deduction all degrade
silently when stock drifts from reality. Track 4 exists to protect it, but
`features.md` offers three different theories of why it drifts, and they want
different fixes:

| Theory | Fix | Size |
|---|---|---|
| Logging shopping is too tedious, so stock never goes up | Grocery-receipt OCR → stock (fully specced; needs `tesseract` as a system dep) | L |
| You don't notice you're out of something until you need it | Staples / low-stock alerts (`is_staple` + `min_quantity` columns, `GET /api/inventory/low`) | M |
| Forward-only actions can't be corrected, so wrong numbers stay wrong | One uniform reverse-apply across cook + grocery submit | M–L |

Decide which theory ticket 03's evidence supports, and therefore what track 4
contains. Possibly none of them — if inventory stays accurate in real use, this
track should be dropped rather than built, and the map records that as a
scoping decision.

### Note

All three change the schema, which is why ticket 08 is gated on this one.
Undo also needs a design decision of its own before it could be built: it is
one uniform reverse operation across cook, grocery, and later receipts — not a
per-action `/undo` route — and possibly a mutation audit trail. The snapshots
it would need already exist (`CookLog.deductions` records
requested/deducted/before/after; `GroceryListItem.applied_quantity/unit`).
