# BHSR Book Series Playbook

Shared reference for the book team in `.claude/agents/`. Every agent reads this first. When this file and the code
disagree on a platform rule, the code wins: `core/hashtags.py` and `core/social_dispatcher.py`.

## The team

| Agent | Job | Writes |
|---|---|---|
| `book-architect` | Turns a block of weeks into a book outline and chapter briefs | `outline.md` |
| `book-writer` | Drafts one chapter from that week's scripts and study guide | `chapters/chNN_Wxx.md` |
| `book-art-director` | Picks, sources and prepares the photos and illustrations | `images/`, `images/image_plan.md` |
| `book-editor` | Developmental edit, scripture and fact check, overlap, captions and credits | `Editorial_Report.md` |
| `book-producer` | Front/back matter, full manuscript, EPUB/DOCX/PDF, KDP listing and print cost | `Manuscript_Full.md`, `build/`, `KDP_Listing.md` |
| `book-launch-strategist` | Launch calendar for a book across all five channels | `marketing/launch_plan.md` |
| `youtube-book-marketer` | YouTube long-form segments, Shorts, Community posts | `marketing/youtube.md` |
| `facebook-book-marketer` | Facebook Reels, Page posts, Watch | `marketing/facebook.md` |
| `tiktok-book-marketer` | TikTok / BookTok videos and captions | `marketing/tiktok.md` |
| `x-book-marketer` | X posts and threads (posted manually) | `marketing/x.md` |
| `threads-book-marketer` | Threads posts | `marketing/threads.md` |

Subagents cannot call each other. The main Claude session runs the order: architect → writer (per chapter) →
art director → editor → writer and art director fixes → producer, with the strategist and channel marketers working
from `outline.md` onward.

## Series map

Series name (working): **Bible Hidden Secrets Revealed**. Author / pen name: **Ezra Keys** (same as the Enoch book).

### Year 1 — two illustrated books (decided 2026-10-07)

Series title **Holy Curiosity**, by Ezra Keys. The saying "curiosity killed the cat" is split across the two books
(see "Book theme"). KDP series field: Holy Curiosity (Bible Hidden Secrets Revealed). 26 chapters per book, one per
week, two parts per book. Working subtitles:

| Book | Weeks | Parts | Working title | Folder |
|---|---|---|---|---|
| One | W01–W26 | I Before Abraham (W01–W13), II Patriarchs & Exodus (W14–W26) | *Holy Curiosity, Book One: 26 Hidden Secrets of the Bible, from Creation to Jericho* | `BHSR_Year1_Book1` |
| Two | W27–W52 | III Kings & Prophets (W27–W39), IV The Cross & the Consummation (W40–W52) | *Holy Curiosity, Book Two: 26 Hidden Secrets of the Bible, from Goliath to the New Jerusalem* | `BHSR_Year1_Book2` |

Book One goes first: it is far better sourced (13 full scripts, 12 thin, 1 missing; scene art for 10 weeks) than
Book Two (11 full scripts, 15 missing; scene art for 3 weeks). Research Book Two's missing weeks, starting with
W44–W49, while Book One is written.

Edition spec (each book):
- Chapters about 2,500 words, up to 3,000 where the week has a full script; a thin-source chapter may run
  2,000–2,300 rather than be padded.
- Trim 7 x 10 in. Interior: **decided later** — prepare color files; convert to grayscale only if the user picks
  black & white. Ask before the final PDF build. Both books use the same interior and design.
- Images: one full-page chapter opener plus 1–2 inline images per chapter, a part-opener image for each part, and
  maps where they help.
- Target about 240–270 pages per book (estimate; test-build three chapters of Book One to measure).
- Each book stands alone: its own introduction, conclusion, study guide, glossary, timeline and Scripture index.
  Cross-book references name the book ("see Book One, Chapter 13").

### Book theme: curiosity (Year 1)

- Epigraphs (page after the title page): Book One, "It is the glory of God to conceal a thing: but the honour of
  kings is to search out a matter." — Proverbs 25:2 (KJV). Book Two, "...which things the angels desire to look
  into." — 1 Peter 1:12 (KJV).
- Book One introduction: curiosity has a dark history in Scripture — Eve reached for the fruit (Genesis 3:6), Lot's
  wife looked back (Genesis 19:26) — yet God hides things so we will search them out (Proverbs 25:2). It opens
  with "curiosity killed the cat".
- Book Two introduction: the men of Beth-shemesh looked into the Ark and died (1 Samuel 6:19); the angels long to
  look into what the cross reveals (1 Peter 1:12). Book Two's conclusion completes the saying, "but satisfaction
  brought it back": curiosity answered in Christ. Not a pun on the resurrection.
- Book One ends on a bridge into Book Two (Jericho's fallen walls → the giant at Elah), not a summary.
- Chapter shape: open a mystery question → follow the clues → the answer, ending on the Christological key.
- The saying appears only in the introductions, conclusions, back covers and marketing — never as a refrain inside
  chapters.
- Marketing pillar #1: "What were you never supposed to look into?"

### Year 1 writing guide (adopted 2026-10-07)

Follow `docs/book_year1_writing_recommendations.md`: voice, chapter shape, Scripture and sources, the "unseen realm"
chapters, the riskiest weeks, structure, images and shareability. Decided by the author:
- Debated questions (angels in Genesis 6, 1948, the "6,000 years"): present each view fairly, then state Ezra Keys'
  leaning and why.
- Discussion questions go in a study guide at the back (two per chapter plus a reading plan), never at chapter ends.
- Jesus, God and angels appear only as silhouettes, light or symbols; no faces.
- Still open: KJV only or WEB where the KJV hides the point; "I" in the introduction and conclusion; Part II
  renamed "Patriarchs, Exodus & the Promised Land"; W01's picture-letter "cross" (drop, or a labelled devotional
  box); a human reviewer for the riskiest weeks; AI chapter openers; color or black & white.

### Years 2 and 3 — format not decided

Either four volumes each (below) or illustrated books like Year 1. Ask the user before planning either year.

| Year | Weeks | Working title | Folder (if a separate volume) |
|---|---|---|---|
| 2 | W53–W65 | The Lost Books | `BHSR_Y2_The_Lost_Books` |
| 2 | W66–W78 | The Unseen Realm | `BHSR_Y2_The_Unseen_Realm` |
| 2 | W79–W91 | Stones That Speak | `BHSR_Y2_Stones_That_Speak` |
| 2 | W92–W104 | The Qumran Library | `BHSR_Y2_The_Qumran_Library` |
| 3 | W105–W117 | Daniel & the Apocalypse | `BHSR_Y3_Daniel_and_the_Apocalypse` |
| 3 | W118–W130 | The Final Acts | `BHSR_Y3_The_Final_Acts` |
| 3 | W131–W143 | Hebrew Secrets | `BHSR_Y3_Hebrew_Secrets` |
| 3 | W144–W156 | Faith Under Fire | `BHSR_Y3_Faith_Under_Fire` |

### Topics covered twice

The weekly series revisits some topics. In the books the later chapter goes deeper and points back to the earlier
one instead of repeating it. Within Year 1 the pairs are a few chapters apart, so cut the repeat hard.

- W37 ↔ W107 Daniel's 70 weeks
- W39 ↔ W95–W96 4Q521 and 4Q246
- W43 ↔ W119 the Red Heifer
- W01, W13 ↔ W66 the Divine Council
- W06–W07 ↔ W53–W54, W75 the Watchers and the Book of Giants
- W50 ↔ W116 the Revelation 12 dragon
- W51 ↔ W117 the 666 mark
- W48 ↔ W155 the Emmaus Road

The Year 2 Enoch material overlaps the existing book *The Watchers and the Word*
(`C:\Projects\books\Book_of_Enoch`). Point readers to it rather than re-covering 1 Enoch at the same depth.

## Where things live

Weekly source material, `C:\Projects\BHSR\Wxx\`:
- `long_form/**/script_30min.txt` (best source, ~4,500 words), else `long_form/**/script.md` or `script.txt`
- `substack/pillar_study_guide.md`, `substack/midweek_digest.md`
- `metadata.json` (theme, year, quarter, captions), `community/community_posts.json` (polls, quote cards)
- `reels/*/script*.txt` — short hooks per week; good teaser material for marketing
- Images: `long_form/**/images/`, `long_form/**/thumbnail*`, `reels/**/` (see "Photos and illustrations")

Week definitions (title, scriptures, Christological key): `core/story_map_definitions.py`.

Not every week has a usable script. Check before writing:
`find C:/Projects/BHSR/Wxx/long_form -name "*script*"`, then check the file really has content (unique words, not a
repeated paragraph). Year 1 at 2026-10-07:
- Full scripts: W01–W03, W05, W06, W08, W09, W11, W12, W15, W16, W18, W25, W29, W32, W35, W36, W38, W41, W43,
  W50–W52. W27's real source is `W27\long_form\1-David_Goliath_1Hour\full_script.md` (not `script.md`).
- Short (1,600–2,000 words): W04, W07, W10 — usable, but research to fill out.
- Boilerplate (about 1,500 words, under 500 unique; one paragraph repeated): W13, W14, W17, W19–W24 — treat as
  research.
- None: W26, W28, W30, W31, W33, W34, W37, W39, W40, W42, W44–W49.
Mark each chapter header `source: script | thin | research`. Weeks without study guides or with mismatched reels
(W26 onward) get no help from those folders either.

Book output: `C:\Projects\books\<Folder>\`. The Enoch book in `C:\Projects\books\Book_of_Enoch\` is the reference
for format, `Editorial_Report.md`, `Marketing_Copy.md` and the build.

Pandoc (not on PATH): `C:\Projects\books\Book_of_Enoch\pandoc\pandoc-3.11\pandoc.exe`. Pillow is installed for
image work.

Store links: `DEFAULT_BHRS_PINNED_COMMENT` in `core/social_dispatcher.py` is the links comment posted after every
upload. Adding a new book's Amazon link there is a code change for the user or the main session, not the agents.

## Book folder layout

```
C:\Projects\books\BHSR_Year1_Book1\
  outline.md                 book-architect
  chapters\ch01_W01.md ...   book-writer (one file per chapter)
  images\                    book-art-director
    image_plan.md            every image: chapter, file, source, license, credit, caption, placement
    downloads.csv            external images waiting for the user's approval
    prompts.json             new FLUX renders needed
    print\  ebook\           prepared files
  Editorial_Report.md        book-editor
  Front_Matter.md            book-producer
  Back_Matter.md             book-producer (includes illustration credits)
  Manuscript_Full.md         book-producer
  build\                     book-producer (.epub .docx .pdf)
  KDP_Listing.md             book-producer
  marketing\
    launch_plan.md           book-launch-strategist
    youtube.md facebook.md tiktok.md x.md threads.md
```

## Chapter spec

- Length: the word target in the book's `outline.md` (Year 1 books: about 2,500, up to 3,000; full-length volumes:
  4,500–5,500). Video narration is the raw material, not the text: remove "in this episode", "on screen", "like and
  subscribe", scene cues and the spoken CTA.
- Structure: opening mystery hook → H2 sections → the Christological key → a closing bridge to the next chapter →
  `## Notes` with sources.
- Image spots: the writer marks 1–2 places where a picture helps the reader with an HTML comment,
  `<!-- image: what the reader should see here -->`. The art director replaces each with the final image.
- Hebrew, Greek and Aramaic deep dives go in callouts so the main narrative flows (lesson from the Enoch editorial
  report):
  `> **Hebrew Insight — *bereshit*:** ...`
- Markdown conventions (set by the Book One pilot chapters 5, 12 and 20; keep every chapter the same):
  - Under the H1, two italic lines for the opener page, copied from the chapter's brief in `outline.md`: the
    mystery question, then `*Key passages: <Old Testament passage>; <New Testament key>*`. Then the hook, which
    must still read on its own.
  - Note markers are pandoc superscripts, `^1^`, numbered in order, with a numbered list under `## Notes`.
  - Debated-claim box: `> **Weighing the Evidence — <topic>:** ...` (100 words or less).
  - Pull-quote: one per chapter as `<!-- pull-quote: ... -->` right after the line it repeats.
  - Where the author's view is needed: `[EZRA KEYS' LEANING: <question>; options: (a) ...; (b) ...]` on its own
    line. Writers never fill it in; the author does.
  - `words:` in the header counts the body from the H1 through the bridge, without notes and HTML comments.
  - Each book numbers its chapters from 1. Until Book Two's outline exists, Book One points to it as "Book Two"
    with no chapter number.
- Style sheet (adopted from the pilot review, 2026-10-08):
  - In notes, abbreviate Bible books (Gen, Exod, Matt, 2 Kgs); in the text, spell them out.
  - No Hebrew or Greek script anywhere, notes included. Transliterate with one scheme: *ch* for ח, *kh* for כ, *ts*
    for צ, an apostrophe for aleph and ayin where needed, Greek *ē* and *ō*.
  - One ellipsis form: "…" with a space either side.
  - Reference works in roman (BDB, HALOT).
  - At most six block quotations per chapter; short inline phrases don't count.
  - Dates: the middle chronology for Mesopotamia; for Egypt, Ian Shaw (ed.), *The Oxford History of Ancient Egypt*
    (Oxford University Press, 2000). Both stated once in the front matter.
  - Notes carry no working instructions. An open item is written `[SOURCE NEEDED: …]` and nothing else.
- Two running files in the book folder:
  - `bibliography.md`: the full Chicago entry for every work cited in short form, added when a work is first
    cited. The producer builds the back-matter bibliography from it.
  - `crossrefs.md`: every "see Chapter N" / "Chapter N has already…" with what the target chapter must contain.
    Writers add to it; the editor checks it before the manuscript is assembled.
- Scripture: quote public-domain translations (KJV, WEB) by default and name the translation in the front matter.
  Quote copyrighted translations (NIV, ESV, NKJV, NLT) only within their publishers' permission limits.
- Dates, manuscript IDs, archaeology and statistics need a source in `## Notes`. Contested claims (Jabal al-Lawz as
  Sinai, the Tall el-Hammam airburst, the Shroud of Turin, Kepler's conjunction) are presented as debated, with the
  main positions, not as settled proof.

## Photos and illustrations

Sources, in order of preference:
1. **The channel's own art** (FLUX renders from the pipeline). Year 1 weeks with long-form scene art at
   2026-10-07: W01–W03, W06, W11, W12, W15, W16, W18, W25, W27, W35, W43 — all 1344 x 768. W04, W05, W14, W17 have
   only 768 x 1344 reel frames; W07–W10, W13, W19–W24 only thumbnails or cards with baked-in headlines (not usable);
   W26, W28–W34, W36–W42, W44–W52 nothing. Thumbnails (1920 x 1080) carry headlines and the logo: never use them.
   These are AI-generated images.
2. **Public-domain art**: Gustave Doré's 1866 Bible engravings (black and white), James Tissot's Bible paintings
   (color), Julius Schnorr von Carolsfeld's *Bible in Pictures*. High-resolution scans are on Wikimedia Commons.
   Faithful photos of 2-D public-domain artworks are public domain in the US.
3. **Archaeology, manuscript photos and maps**: public domain, CC0, CC BY or CC BY-SA only, with the credit the
   license requires. No NC (non-commercial) or ND (no-derivatives) licenses, no stock or search-engine images
   without a license.
4. **New renders** for chapters still without art, and for every chapter opener: FLUX prompts in the house formula
   (no text or lettering, no gore), rendered by the user's pipeline.

Jesus, God and angels appear only as silhouettes, light or symbols, never with faces (decided 2026-10-07).

Print resolution is 300 DPI at the printed size:
- Text-width image on a 7 x 10 page (about 5.75 in): at least 1,725 px wide. The 1344 x 768 scene renders need a 2x
  upscale (Lanczos), then a sharpness check at 100%.
- Full-page opener inside the margins (about 5.75 x 8.5 in): at least 1,725 x 2,550 px. Render openers new, in
  portrait, at that size or larger; don't crop or upscale existing landscape or reel frames to full page.
- Default is no bleed. If the user wants full-bleed openers, the whole PDF becomes 7.125 x 10.25 in.
- Black & white interior: convert to grayscale and lift contrast; check that dark scenes still read.
- Ebook copies: long edge about 1,600 px, JPEG quality about 85. Amazon charges a per-MB delivery fee on ebooks
  sold at the 70% royalty, so image weight costs money on every sale.

Agents don't download external files. External images go in `images/downloads.csv` (URL, license, credit, target
filename); the user approves the list and the main session fetches it.

## Print cost (Amazon.com, from KDP's printing-cost help page, checked 2026-10-07)

Large trim (7 x 10 is large: wider than 6.12 in): fixed $1.00 plus per page —
black ink $0.017 (110–828 pages), standard color $0.0402 (72–600 pages), premium color $0.08 (42–828 pages).
Paperback royalty is 60% of list price minus printing cost. Recheck the rates before setting a price.

At 250 pages (one Year 1 book): black ink ≈ $5.25, standard color ≈ $11.05, premium color ≈ $21.00 per copy.

## House formats

- Caption format (all platforms): `HOOK IN CAPITALS` / scripture references / description / hashtags.
- No URLs, store lines or "link in bio" lines in any caption. The pipeline strips them
  (`SocialDispatcher.strip_promo_text`); links go in the comment posted right after publishing.
- Spoken CTA for video scripts: "Our books and sacred art merch are linked in the bio and comments."
  (`scripts/apply_books_merch_cta.py`)
- Hook formula: the 3-part contrast in `C:\Projects\BHSR\POSTING_STRATEGY.md` (common assumption → scriptural
  shatter → hidden proof → bridge).
- Posting windows (EST): 6:30–8:00, 12:00–13:00, 19:00–21:00. Long-form Saturday/Sunday 8:00; reels Mon–Fri.
- In marketing copy, name the book by its title and chapter ("Chapter 7 of *Holy Curiosity, Book One*"), not a volume number.

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
- Write only inside the book folder. Don't edit `C:\Projects\BHSR` week files or this repository's code; copy
  images out of the week folders, never move or alter the originals.
- Don't download external files; list them in `images/downloads.csv` for the user to approve.
- Reviews: never offer payment, gifts or discounts for reviews. Advance reader copies are free with no review
  required; reviewers who post disclose the free copy.
- No invented endorsements, review quotes, sales figures or "bestselling" claims. Use a ranking only when the user
  gives one.
- KDP asks whether text, images or translations are AI-generated. The channel's FLUX art is AI-generated, so the
  listing checklist flags this for the user to answer truthfully.
- Windows console: plain ASCII log tags in any script output (`[OK]`, `[WARN]`), as in the production guide.
