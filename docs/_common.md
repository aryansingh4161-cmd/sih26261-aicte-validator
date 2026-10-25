## How every Sunday card works (read once)
- A **window** = the time from your first message to Claude until it resets 5 hours later. Send your first message of Window 1 at about 10:30, Window 2 at about 15:30, Window 3 at about 20:30. About 1.5 hours of real AI use fits in each window; the cards are sized for that. If Claude hits its limit mid-card, paste the SAME card into ChatGPT or Gemini (cards are self-contained) and carry on.
- **PASTE KIT for code cards** = three things pasted as your FIRST message in a NEW chat: (1) the CONTEXT block (`docs/CONTEXT_FULL.md`), (2) the full text of `pramaan/schemas.py`, (3) the lines of `docs/CONTRACTS.md` your card names. Then send the card's EXACT PROMPT as the second message. If your tool has Projects, put (1) and (2) in the Project once and skip them later.
- One file per message. Save it with the EXACT file name and folder the card says. Run the SMOKE TEST. If it passes, send the file to Aryan on WhatsApp (file name unchanged) and write "<file> passes". Aryan merges.
- **Two-failure rule:** if the same error survives two fix attempts, STOP and message Aryan with: card number, the command you ran, the full error. Do not spend a third attempt, and never change data shapes to "make it work".
- **FIX PROMPT (same for every card):**
```
I ran: <the command>. It printed this error: <paste the WHOLE error>. Explain in one plain sentence what went wrong, then give me the WHOLE corrected file <file name>. Do not change any other file and do not change any data shape in schemas.py.
```
- Clock: tech freeze is Monday 23:00. Tuesday is slides and video only.
