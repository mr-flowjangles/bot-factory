# v2.1.0 — Cost Optimization + Content Expansion (2026-03-26)

## Summary

Cost optimization through server-side conversation history capping, plus major knowledge base expansion: complete pentatonic/blues scale boxes (all 5 positions) and full modal theory coverage (7 modes with tab patterns).

## Cost Optimization

- **Server-side conversation history cap** — `build_messages()` now slices to the last 6 messages (3 exchanges) before sending to Bedrock, regardless of what the client sends. Reduces input tokens on every request and guards against oversized payloads.
- Prompt caching (`cachePoint` on system prompt) remains in place from v2.0.6.

## Chat UX

- **Input lock during streaming** — Chat input is disabled while a response is streaming. Prevents users from sending overlapping requests. Re-enables with focus on completion or error.
- **Character-by-character rendering** — Token stream now renders one character at a time (50ms interval) instead of dumping whole tokens at once. Smoother visual experience.

## Knowledge Base Expansion

### Scales (03-scales.yml — deployed to S3, not in git)
- **Minor pentatonic:** Added boxes 3, 4, 5 (was only 1-2). Fixed box 2 D string (fret 9=B corrected to fret 10=C).
- **Major pentatonic:** Added boxes 2, 3, 4, 5. Fixed box 1 — removed F# notes that are in G major but not G major pentatonic.
- **Blues scale:** Added boxes 2, 3, 4, 5. Fixed box 1 — blue note was on D string fret 8 (Bb, wrong); moved to correct positions: G string fret 8 and A string fret 6 (Eb).

### Modes (10-modes.yml — new file, deployed to S3)
- **Modes vs Scales explanation** — What modes are, how they differ from scales, the 7 modes listed with character/mood, practical usage guide.
- **All 7 mode patterns** with verified tab diagrams:
  - C Ionian (major scale) — root on 6th string 8th fret
  - D Dorian — root on 6th string 10th fret
  - E Phrygian — root on open 6th string
  - F Lydian — root on 6th string 1st fret
  - G Mixolydian — root on 6th string 3rd fret
  - A Aeolian (natural minor) — root on 6th string 5th fret
  - B Locrian — root on 6th string 7th fret
- Each mode includes: formula, character description, practical usage tips, artist references.

## Prompt Updates (prompt.yml)

- **Scale transposition rule** — When a user asks for a pentatonic scale in any key, use the A minor pattern and shift fret numbers to match. Teaches the moveable shape concept.
- **Follow-up handling** — Added rule for vague follow-ups ("how do you use it?", "tell me more") to check conversation history for topic context instead of asking the user to clarify.

## Changed

- `factory/core/chatbot.py` — Server-side history cap (last 6 messages) in `build_messages()`
- `app/bot_scripts/chat.js` — Input lock during streaming, character-by-character rendering (50ms)
- `scripts/bots/the-fret-detective/prompt.yml` — Scale transposition + follow-up handling rules
- `scripts/bots/the-fret-detective/data/03-scales.yml` — 12 new box patterns + 3 fixes (S3 only)
- `scripts/bots/the-fret-detective/data/10-modes.yml` — New file: 8 entries (S3 only)
- `todo.md` — Cost optimization tracking

## Embedding Count

142 → 172 embeddings (+30: 12 scale box expansions via existing entries, 7 modes, rest from corrected entries generating new embeddings on re-embed)
