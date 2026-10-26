// UI strings: English is the source; hi, bn, ta, mr come from config/i18n/*.json (pre-translated offline with IndicTrans2,
// copied by `npm run i18n`). Other languages show English UI text with a small note. Dynamic text arrives translated from
// the API (live) or the snapshot (demo).
import hi from "./i18n/hi.json";
import bn from "./i18n/bn.json";
import ta from "./i18n/ta.json";
import mr from "./i18n/mr.json";

export const LANGUAGES: { id: string; name: string; native: string }[] = [
  { id: "en", name: "English", native: "English" }, { id: "hi", name: "Hindi", native: "हिन्दी" }, { id: "bn", name: "Bengali", native: "বাংলা" },
  { id: "mr", name: "Marathi", native: "मराठी" }, { id: "te", name: "Telugu", native: "తెలుగు" }, { id: "ta", name: "Tamil", native: "தமிழ்" },
  { id: "gu", name: "Gujarati", native: "ગુજરાતી" }, { id: "kn", name: "Kannada", native: "ಕನ್ನಡ" }, { id: "ml", name: "Malayalam", native: "മലയാളം" },
  { id: "or", name: "Odia", native: "ଓଡ଼ିଆ" }, { id: "pa", name: "Punjabi", native: "ਪੰਜਾਬੀ" }, { id: "as", name: "Assamese", native: "অসমীয়া" },
  { id: "ur", name: "Urdu", native: "اردو" },
];
const TABLES: Record<string, Record<string, string>> = { hi, bn, ta, mr };
export const hasUiTable = (lang: string) => lang === "en" || lang in TABLES;
export const isRtl = (lang: string) => lang === "ur";

export function translate(lang: string, text: string): string {
  if (lang === "en") return text;
  return TABLES[lang]?.[text] ?? text;
}

const FONTS: Record<string, () => Promise<unknown>> = {
  hi: () => Promise.all([import("@fontsource/noto-sans-devanagari/400.css"), import("@fontsource/noto-sans-devanagari/500.css")]),
  mr: () => Promise.all([import("@fontsource/noto-sans-devanagari/400.css"), import("@fontsource/noto-sans-devanagari/500.css")]),
  bn: () => Promise.all([import("@fontsource/noto-sans-bengali/400.css"), import("@fontsource/noto-sans-bengali/500.css")]),
  as: () => Promise.all([import("@fontsource/noto-sans-bengali/400.css"), import("@fontsource/noto-sans-bengali/500.css")]),
  ta: () => Promise.all([import("@fontsource/noto-sans-tamil/400.css"), import("@fontsource/noto-sans-tamil/500.css")]),
  te: () => Promise.all([import("@fontsource/noto-sans-telugu/400.css"), import("@fontsource/noto-sans-telugu/500.css")]),
  gu: () => Promise.all([import("@fontsource/noto-sans-gujarati/400.css"), import("@fontsource/noto-sans-gujarati/500.css")]),
  kn: () => Promise.all([import("@fontsource/noto-sans-kannada/400.css"), import("@fontsource/noto-sans-kannada/500.css")]),
  ml: () => Promise.all([import("@fontsource/noto-sans-malayalam/400.css"), import("@fontsource/noto-sans-malayalam/500.css")]),
  or: () => Promise.all([import("@fontsource/noto-sans-oriya/400.css"), import("@fontsource/noto-sans-oriya/500.css")]),
  pa: () => Promise.all([import("@fontsource/noto-sans-gurmukhi/400.css"), import("@fontsource/noto-sans-gurmukhi/500.css")]),
  ur: () => Promise.all([import("@fontsource/noto-nastaliq-urdu/400.css"), import("@fontsource/noto-nastaliq-urdu/500.css")]),
};
const SCRIPT_FAMILY: Record<string, string> = { hi: "Noto Sans Devanagari", mr: "Noto Sans Devanagari", bn: "Noto Sans Bengali", as: "Noto Sans Bengali",
  ta: "Noto Sans Tamil", te: "Noto Sans Telugu", gu: "Noto Sans Gujarati", kn: "Noto Sans Kannada", ml: "Noto Sans Malayalam",
  or: "Noto Sans Oriya", pa: "Noto Sans Gurmukhi", ur: "Noto Nastaliq Urdu" };

/** Load the Noto font for the chosen script (only that one) and point --font-script at it. */
export async function applyLanguage(lang: string) {
  document.documentElement.lang = lang;
  document.documentElement.dir = isRtl(lang) ? "rtl" : "ltr";
  if (FONTS[lang]) await FONTS[lang]();
  document.documentElement.style.setProperty("--font-script", SCRIPT_FAMILY[lang] ? `"${SCRIPT_FAMILY[lang]}", sans-serif` : "sans-serif");
}
