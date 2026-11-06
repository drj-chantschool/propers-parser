# GRADUALE — content log

Append-only. Newest at the bottom. `❓ HELD` = waiting on an intake_queue answer; `⛔` = error; `⏸` = session-limit backoff.

- 2026-10-22 14:36 — Queue created with the 11 Addenda Masses (printed 919-921). See BOOK.md § Addenda.
- 2026-10-22 17:57 — ❓ HELD NAT-EPI-00-0-vigil: intake_queue #36 Addenda no-text bbox
- 2026-10-22 17:57 — ❓ HELD PASC-ASC-06-5-vigil: intake_queue #36 Addenda no-text bbox
- 2026-10-22 17:57 — ❓ HELD teresa-benedicta-of-the-cross: intake_queue #36 Addenda no-text bbox
- 2026-10-22 17:57 — batch 1: NAT-EPI-00-0-vigil, PASC-ASC-06-5-vigil, teresa-benedicta-of-the-cross held (0 rows); specs written, not dry-run clean
- 2026-10-23 00:32 — ⏸ driven 2026-10-23: no batch run; all 11 Addenda units blocked on unanswered intake_queue #36 (no-text bbox loader); 8 pending not claimed (none could dry-run)
- 2026-10-23 17:48 — ↩ intake_queue #36 answered: released NAT-EPI-00-0-vigil, PASC-ASC-06-5-vigil, teresa-benedicta-of-the-cross to pending
- 2026-10-23 17:48 — ✅ intake_queue #36 resolved: load_graduale_propers.compute_bbox falls back to band x SCALE at full page width when a page has no text layer (CamScanner watermark ignored); NAT-EPI-00-0-vigil, PASC-ASC-06-5-vigil, teresa-benedicta-of-the-cross now dry-run clean (PASC-ASC-06-5-vigil still shows the advisory COMPLETENESS 'missing co' warning for its cycle-specific communions; reviewer to accept)
- 2026-10-24 05:56 — 🔧 load_graduale_propers.build_rows: lit_epoch kind='mass' now a leaf (with day/common) — cycle_sun chants on PASC-ASC-06-5-vigil were being promoted to non-existent slug PASC-ASC-06-5-vigil-1 (wkday=1); now stay on the vigil slug with wkday=4
- 2026-10-24 05:56 — ⚠ accepted PASC-ASC-06-5-vigil COMPLETENESS 'missing co': CO is printed per year (Psallite Domino A/B, Pater cum essem C), so every year has one
- 2026-10-24 05:56 — batch 2 (stage content, driven): NAT-EPI-00-0-vigil loaded (5 rows), PASC-ASC-06-5-vigil loaded (8 rows), teresa-benedicta-of-the-cross loaded (5 rows); existing specs reviewed against p919, no producers spawned
- 2026-10-24 18:07 — batch 3 (stage content, driven): st-maximilian-kolbe no_rows (Addenda p919-920 citations identical to the loaded p596 rows), andrew-kim-taegon-paul-chong-hasang loaded (5 rows), pio-of-pietrelcina loaded (5 rows); director wrote the pure page cross-reference specs from p920 (one unambiguous index row per cited part), no producers spawned
- 2026-10-25 06:18 — ⚠ accepted: pope-john-xxiii and john-paul-ii print 'Mem.' but lit_epoch rank_code stays OPTIONAL_MEMORIAL (the General Calendar rank; same as teresa-benedicta-of-the-cross). Not raised.
- 2026-10-25 06:18 — batch 4 (stage content, driven): pope-john-xxiii loaded (5 rows), john-paul-ii loaded (5 rows, p920-921), andrew-dung-lac loaded (5 rows); director wrote the page cross-reference specs from p920-921 (one index row per cited part; 'Ecce sacerdos magnus'/'Loquetur Dominus' matched the index forms 'Ecce sacerdos'/'Loquetur Dominus pacem'), no producers spawned
- 2026-10-27 18:03 — ❓ HELD pontons-rochefort-martyrs-osb: intake_queue #39 OSB Addenda epochs
- 2026-10-27 18:03 — ❓ HELD omnium-sanctorum-osb: intake_queue #39 OSB Addenda epochs
- 2026-10-27 18:03 — batch 5 (stage content, driven): pontons-rochefort-martyrs-osb, omnium-sanctorum-osb held (0 rows) pending #39; no producers spawned
- 2026-11-05 21:04 — ↩ intake_queue #39 answered: released pontons-rochefort-martyrs-osb, omnium-sanctorum-osb to pending
- 2026-11-05 21:05 — ✅ intake_queue #39 resolved: created lit_epoch/lit_epoch_tree/proper_of_saints rows pontons-rochefort-martyrs-osb (rank NULL/UNDETERMINED) and omnium-sanctorum-osb (MEMORIAL), jurisdiction OSB
