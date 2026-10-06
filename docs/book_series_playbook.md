# BHSR Book Series Playbook

Shared reference for the book team in `.claude/agents/`. Every agent reads this first. When this file and the code
disagree on a platform rule, the code wins: `core/hashtags.py` and `core/social_dispatcher.py`.

## The team

| Agent | Job | Writes |
|---|---|---|
| `book-architect` | Turns a 13-week block into a volume outline and chapter briefs | `outline.md` |
| `book-writer` | Drafts one chapter from that week's scripts and study guide | `chapters/chNN_Wxx.md` |
| `book-editor` | Developmental edit, scripture and fact check, cross-chapter overlap | `Editorial_Report.md` |
| `book-producer` | Front/back matter, full manuscript, EPUB/DOCX/PDF, KDP listing | `Manuscript_Full.md`, `build/`, `KDP_Listing.md` |
| `book-launch-strategist` | Launch calendar for a volume across all five channels | `marketing/launch_plan.md` |
| `youtube-book-marketer` | YouTube long-form segments, Shorts, Community posts | `marketing/youtube.md` |
| `facebook-book-marketer` | Facebook Reels, Page posts, Watch | `marketing/facebook.md` |
| `tiktok-book-marketer` | TikTok / BookTok videos and captions | `marketing/tiktok.md` |
| `x-book-marketer` | X posts and threads (posted manually) | `marketing/x.md` |
| `threads-book-marketer` | Threads posts | `marketing/threads.md` |

Subagents cannot call each other. The main Claude session runs the order: architect → writer (×13) → editor →
writer revisions → producer, with the strategist and channel marketers working from `outline.md` onward.

## Series map

12 volumes, 13 chapters each, one chapter per week. Titles are working titles until the user approves them.
Series name (working): **Bible Hidden Secrets Revealed**. Author / pen name: **not set yet** — ask the user before
the first build (the Enoch book uses "Ezra Keys").

| Vol | Weeks | Working title | Folder |
|---|---|---|---|
| 1 | W01–W13 | Before Abraham | `BHSR_Vol01_Before_Abraham` |
| 2 | W14–W26 | Patriarchs & Exodus | `BHSR_Vol02_Patriarchs_and_Exodus` |
| 3 | W27–W39 | Kings & Prophets | `BHSR_Vol03_Kings_and_Prophets` |
| 4 | W40–W52 | The Cross & the Consummation | `BHSR_Vol04_The_Cross_and_the_Consummation` |
| 5 | W53–W65 | The Lost Books | `BHSR_Vol05_The_Lost_Books` |
| 6 | W66–W78 | The Unseen Realm | `BHSR_Vol06_The_Unseen_Realm` |
| 7 | W79–W91 | Stones That Speak | `BHSR_Vol07_Stones_That_Speak` |
| 8 | W92–W104 | The Qumran Library | `BHSR_Vol08_The_Qumran_Library` |
| 9 | W105–W117 | Daniel & the Apocalypse | `BHSR_Vol09_Daniel_and_the_Apocalypse` |
| 10 | W118–W130 | The Final Acts | `BHSR_Vol10_The_Final_Acts` |
| 11 | W131–W143 | Hebrew Secrets | `BHSR_Vol11_Hebrew_Secrets` |
| 12 | W144–W156 | Faith Under Fire | `BHSR_Vol12_Faith_Under_Fire` |

Year boxsets later: Vols 1–4, 5–8, 9–12.

### Topics covered twice

The weekly series revisits some topics. In the books the later chapter goes deeper and points back to the earlier
one ("see Volume 3, Chapter 11") instead of repeating it.

- W37 ↔ W107 Daniel's 70 weeks
- W39 ↔ W95–W96 4Q521 and 4Q246
- W43 ↔ W119 the Red Heifer
- W01, W13 ↔ W66 the Divine Council
- W06–W07 ↔ W53–W54, W75 the Watchers and the Book of Giants
- W50 ↔ W116 the Revelation 12 dragon
- W51 ↔ W117 the 666 mark
- W48 ↔ W155 the Emmaus Road

Volume 5 also overlaps the existing book *The Watchers and the Word* (`C:\Projects\books\Book_of_Enoch`). Point
readers to it rather than re-covering 1 Enoch at the same depth.

## Where things live

Weekly source material, `C:\Projects\BHSR\Wxx\`:
- `long_form/**/script_30min.txt` (best source, ~4,500 words), else `long_form/**/script.md` or `script.txt`
- `substack/pillar_study_guide.md`, `substack/midweek_digest.md`
- `metadata.json` (theme, year, quarter, captions), `community/community_posts.json` (polls, quote cards)
- `reels/*/script*.txt` — five short hooks per week; good teaser material for marketing

Week definitions (title, scriptures, Christological key): `core/story_map_definitions.py`.

Not every week has scripts yet. Check before writing:
`find C:/Projects/BHSR/Wxx/long_form -name "script*"`. At setup (2026-10-04) long-form scripts existed for
W01–W25, W27, W29, W32, W35, W36, W38, W41, W43, W50–W52, W73, W111, W112. A chapter for a week without scripts is
written from the story map and Scripture and marked `source: research` in its header.

Book output: `C:\Projects\books\<Folder>\`. The Enoch book in `C:\Projects\books\Book_of_Enoch\` is the reference
for format, `Editorial_Report.md`, `Marketing_Copy.md` and the build.

Pandoc (not on PATH): `C:\Projects\books\Book_of_Enoch\pandoc\pandoc-3.11\pandoc.exe`.

Store links: `DEFAULT_BHRS_PINNED_COMMENT` in `core/social_dispatcher.py` is the links comment posted after every
upload. Adding a new volume's Amazon link there is a code change for the user or the main session, not the agents.

## Volume folder layout

```
C:\Projects\books\BHSR_Vol01_Before_Abraham\
  outline.md                 book-architect
  chapters\ch01_W01.md ...   book-writer (13 files)
  Editorial_Report.md        book-editor
  Front_Matter.md            book-producer
  Back_Matter.md             book-producer
  Manuscript_Full.md         book-producer
  build\                     book-producer (.epub .docx .pdf)
  KDP_Listing.md             book-producer
  marketing\
    launch_plan.md           book-launch-strategist
    youtube.md facebook.md tiktok.md x.md threads.md
```

## Chapter spec

- 4,500–5,500 words of reading prose. Video narration is the raw material, not the text: remove "in this
  episode", "on screen", "like and subscribe", scene cues and the spoken CTA.
- Structure: opening mystery hook → H2 sections → the Christological key → a closing bridge to the next chapter →
  `## Notes` with sources.
- Hebrew, Greek and Aramaic deep dives go in callouts so the main narrative flows (lesson from the Enoch editorial
  report):
  `> **Hebrew Insight — *bereshit*:** ...`
- Scripture: quote public-domain translations (KJV, WEB) by default and name the translation in the front matter.
  Quote copyrighted translations (NIV, ESV, NKJV, NLT) only within their publishers' permission limits.
- Dates, manuscript IDs, archaeology and statistics need a source in `## Notes`. Contested claims (Jabal al-Lawz as
  Sinai, the Tall el-Hammam airburst, the Shroud of Turin, Kepler's conjunction) are presented as debated, with the
  main positions, not as settled proof.

## House formats

- Caption format (all platforms): `HOOK IN CAPITALS` / scripture references / description / hashtags.
- No URLs, store lines or "link in bio" lines in any caption. The pipeline strips them
  (`SocialDispatcher.strip_promo_text`); links go in the comment posted right after publishing.
- Spoken CTA for video scripts: "Our books and sacred art merch are linked in the bio and comments."
  (`scripts/apply_books_merch_cta.py`)
- Hook formula: the 3-part contrast in `C:\Projects\BHSR\POSTING_STRATEGY.md` (common assumption → scriptural
  shatter → hidden proof → bridge).
- Posting windows (EST): 6:30–8:00, 12:00–13:00, 19:00–21:00. Long-form Saturday/Sunday 8:00; reels Mon–Fri.

## Platform rules (from the code)

| Platform | Caption limit | Hashtags | Notes |
|---|---|---|---|
| YouTube | Title ≤100, description ≤5,000, no `<` `>` | ≤15 | Shorts "Related video" → long-form; Community posts |
| Facebook | — | ≤30 (3–5 reads better) | Reels, Page posts, Watch; links in the first comment |
| TikTok | ≤2,200 | ≤30 | "murder/slaughter/suicide" softened; sensitive tags dropped |
| Threads | ≤500 | 1 (becomes the topic) | Vertical video ≤5 min only; sensitive tags dropped |
| X | ≤280 | ≤2 | No X uploader yet: every X post is posted by hand |

Sensitive tag terms dropped on TikTok, Threads and Instagram (substring match): lucifer, satan, demon, warfare,
devil, murder, slaughter. If every tag is dropped the pipeline falls back to #BibleSecrets #ScriptureUncovered
#BibleStudy #BiblicalTruth.

### Checking captions against the pipeline

Channel marketers run their final captions through the pipeline's own builders, so the draft is exactly what would
be posted. These calls are pure text functions with no network or file access; nothing else in
`core/social_dispatcher.py` may be called.

```bash
cd C:/Projects/AI-Content-Generation-Pipeline && PYTHONIOENCODING=utf-8 python -c "
from core.social_dispatcher import SocialDispatcher as SD
hook, body, refs, tags = 'HOOK IN CAPITALS', 'Description...', 'Genesis 3:15', '#BibleSecrets #BookTok'
for name, cap in [('youtube', SD.build_youtube_description(hook, body, hashtags=tags, scriptures=refs)),
                  ('facebook', SD.build_facebook_caption(hook, body, hashtags=tags, scriptures=refs)),
                  ('tiktok', SD.build_tiktok_caption(hook, body, hashtags=tags, scriptures=refs)),
                  ('threads', SD.build_threads_caption(hook, body, hashtags=tags, scriptures=refs)),
                  ('x', SD.build_x_post(hook, body, hashtags=tags))]:
    print(f'--- {name} ({len(cap)} chars)'); print(cap)
print(SD.sanitize_title_for_youtube('Title to check'))
"
```

If the builder trims the body or drops a tag, rewrite the draft so it fits rather than relying on the trim.

## Guardrails (every agent)

- Draft only. Never run publishing code (`core/social_dispatcher.py`, the uploaders, n8n webhooks), never post, never
  upload to KDP or any store, never send email or DMs. The user publishes.
- Write only inside the volume folder. Don't edit `C:\Projects\BHSR` week files or this repository's code.
- Reviews: never offer payment, gifts or discounts for reviews. Advance reader copies are free with no review
  required; reviewers who post disclose the free copy.
- No invented endorsements, review quotes, sales figures or "bestselling" claims. Use a ranking only when the user
  gives one.
- KDP asks whether text, images or translations are AI-generated. The listing checklist flags this for the user to
  answer truthfully.
- Windows console: plain ASCII log tags in any script output (`[OK]`, `[WARN]`), as in the production guide.
