# Extension pack (synthetic)

Demonstrates adding a customer, an industry, a country and a service line with data and config only.

- Customer CUST004 "Baltic Harbour Hotels" (Hospitality), 5 hotels: Helsinki, Turku (Finland), Tallinn, Tartu, Pärnu (Estonia). All served by laundry L002.
- New service line "Mats": products P2001 Entrance Mat Standard and P2002 Logo Mat. Mats have no wearers (`active_wearers = 0`).
- The hotels also rent workwear P1001 and P1002 from the main pack. Repairs exist only for those.
- Monthly volume is well below 15,000 kg, so check C1 (customer kg vs laundry kg) still flags only L003.
- 2025, 12 months. All values are SYNTHETIC. Cross-border delivery is not distance-modelled.

Regenerate (deterministic, seed 2026): `python scripts/make_extension_pack.py --out data/extension_pack`

Registered in `config/sources.yaml`; set `VR_EXTENSIONS=off` to disable it.
