// Material Symbols (filled, outlined family), self-hosted SVG. Only the icons the app uses are imported.
import type { CSSProperties } from "react";
import inbox from "@material-symbols/svg-400/outlined/inbox-fill.svg?raw";
import calendar_month from "@material-symbols/svg-400/outlined/calendar_month-fill.svg?raw";
import description from "@material-symbols/svg-400/outlined/description-fill.svg?raw";
import history from "@material-symbols/svg-400/outlined/history-fill.svg?raw";
import bar_chart from "@material-symbols/svg-400/outlined/bar_chart-fill.svg?raw";
import search from "@material-symbols/svg-400/outlined/search-fill.svg?raw";
import dark_mode from "@material-symbols/svg-400/outlined/dark_mode-fill.svg?raw";
import light_mode from "@material-symbols/svg-400/outlined/light_mode-fill.svg?raw";
import translate from "@material-symbols/svg-400/outlined/translate-fill.svg?raw";
import keyboard_arrow_down from "@material-symbols/svg-400/outlined/keyboard_arrow_down-fill.svg?raw";
import undo from "@material-symbols/svg-400/outlined/undo-fill.svg?raw";
import visibility from "@material-symbols/svg-400/outlined/visibility-fill.svg?raw";
import check_circle from "@material-symbols/svg-400/outlined/check_circle-fill.svg?raw";
import do_not_disturb_on from "@material-symbols/svg-400/outlined/do_not_disturb_on-fill.svg?raw";
import download from "@material-symbols/svg-400/outlined/download-fill.svg?raw";
import arrow_forward from "@material-symbols/svg-400/outlined/arrow_forward-fill.svg?raw";
import verified_user from "@material-symbols/svg-400/outlined/verified_user-fill.svg?raw";
import refresh from "@material-symbols/svg-400/outlined/refresh-fill.svg?raw";
import open_in_new from "@material-symbols/svg-400/outlined/open_in_new-fill.svg?raw";
import close from "@material-symbols/svg-400/outlined/close-fill.svg?raw";
import chat from "@material-symbols/svg-400/outlined/chat-fill.svg?raw";
import bookmark from "@material-symbols/svg-400/outlined/bookmark-fill.svg?raw";
import location_on from "@material-symbols/svg-400/outlined/location_on-fill.svg?raw";
import photo_camera from "@material-symbols/svg-400/outlined/photo_camera-fill.svg?raw";
import print from "@material-symbols/svg-400/outlined/print-fill.svg?raw";
import logout from "@material-symbols/svg-400/outlined/logout-fill.svg?raw";
import task_alt from "@material-symbols/svg-400/outlined/task_alt-fill.svg?raw";
import error from "@material-symbols/svg-400/outlined/error-fill.svg?raw";
import cloud_off from "@material-symbols/svg-400/outlined/cloud_off-fill.svg?raw";
import keyboard from "@material-symbols/svg-400/outlined/keyboard-fill.svg?raw";
import check_box from "@material-symbols/svg-400/outlined/check_box-fill.svg?raw";
import check_box_outline_blank from "@material-symbols/svg-400/outlined/check_box_outline_blank-fill.svg?raw";
import chevron_right from "@material-symbols/svg-400/outlined/chevron_right-fill.svg?raw";
import person from "@material-symbols/svg-400/outlined/person-fill.svg?raw";
import arrow_back from "@material-symbols/svg-400/outlined/arrow_back-fill.svg?raw";
import gavel from "@material-symbols/svg-400/outlined/gavel-fill.svg?raw";
import warning from "@material-symbols/svg-400/outlined/warning-fill.svg?raw";
const SVG: Record<string, string> = { inbox, calendar_month, description, history, bar_chart, search, dark_mode, light_mode, translate, keyboard_arrow_down, undo, visibility, check_circle, do_not_disturb_on, download, arrow_forward, verified_user, refresh, open_in_new, close, chat, bookmark, location_on, photo_camera, print, logout, task_alt, error, cloud_off, keyboard, check_box, check_box_outline_blank, chevron_right, person, arrow_back, gavel, warning };
export type IconName = keyof typeof SVG;
export function Icon({ name, size, className, style, label }: { name: string; size?: number; className?: string; style?: CSSProperties; label?: string }) {
  const svg = (SVG[name] || "").replace("<svg ", `<svg aria-hidden="true" focusable="false" ${size ? `style="width:${size}px;height:${size}px"` : ""} `);
  return <span className={"ic " + (className || "")} style={{ display: "inline-flex", ...style }} role={label ? "img" : undefined} aria-label={label}
    dangerouslySetInnerHTML={{ __html: svg }} />;
}
