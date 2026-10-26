// Copies the pre-translated UI tables (config/i18n/*.json, built offline by tools/build_translations.py) into the web app.
// Entries with an em dash (old Streamlit page titles) are left out: the web copy uses none (DESIGN_SYSTEM.md section 8).
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
for (const f of readdirSync("../config/i18n")) {
  const table = JSON.parse(readFileSync(`../config/i18n/${f}`, "utf8"));
  const kept = Object.fromEntries(Object.entries(table).filter(([k, v]) => !k.includes("\u2014") && !String(v).includes("\u2014")));
  writeFileSync(`src/i18n/${f}`, JSON.stringify(kept, null, 1));
}
console.log("copied", readdirSync("src/i18n").length, "language tables");
