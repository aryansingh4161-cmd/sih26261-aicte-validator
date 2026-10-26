// Copies the pre-translated UI tables (config/i18n/*.json, built offline by tools/build_translations.py) into the web app.
import { cpSync, readdirSync } from "node:fs";
for (const f of readdirSync("../config/i18n")) cpSync(`../config/i18n/${f}`, `src/i18n/${f}`);
console.log("copied", readdirSync("src/i18n").length, "language tables");
