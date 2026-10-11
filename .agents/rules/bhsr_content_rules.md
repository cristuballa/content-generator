# BHSR Content & Video Generation Guidelines

These rules apply whenever drafting scripts, generating episode metadata, or creating 16:9 documentary videos and vertical Reels/Shorts for Bible Hidden Secrets Revealed (BHSR).

## 1. The 3-Second Hook & First Moments (Zero Fluff)
* **The 3-Second Invariant:** Avoid slow theological wind-ups, greetings, or static title cards. The first 3 seconds (0:00 – 0:03) must have:
  1. An alarming/surprising spoken question or counter-intuitive statement (e.g. *"What was God doing for eternity before Genesis 1?"* or *"The first question ever asked in the Bible came from the serpent. And it was a trap."*).
  2. Large, high-contrast on-screen hook text: Pure White + Vibrant Electric Yellow (`#FFE100`) with heavy drop-shadows.
  3. Fast visual transition / instant dynamic cut to stop thumb-scrolling cold.
* **No Intros:** Do NOT include animated channel logos, music stings, or creator greetings (*"Welcome back to the channel"* or *"Today we are going to talk about..."*) in the first 15 seconds.
* **Fulfill the Promise:** The opening lines must directly validate the question posed in the video title and thumbnail immediately (0:03 onward).

## 2. Retention, Call-to-Action (CTA) & Modular Advertisement Architecture
* **Short-Form Clean Structural Timeline (Reels / Shorts / TikTok):**
  - **0:00 – 0:03 | The Hook (Zero Fluff):** High-curiosity question or shocking biblical premise (0 fluff, White + Electric Yellow `#FFE100`, immediate visual cut, no channel intro).
  - **0:03 – ~80% | Deep Scriptural Revelation:** Fulfill the hook's promise using ancient manuscripts (Dead Sea Scrolls, Septuagint, Hebrew roots), theological tension, and rapid narrative momentum. Zero early begging or self-promotion.
  - **~80% – ~95% | Value-Driven Engagement Ask (Saves & Shares Priority):** Algorithmic catalyst prioritizing Shares & Saves before monetization:
    - *Doc-linked reels (Mon–Fri episode tie-ins):* `"Watch the full episode on our channel, and save this so you don't lose this scripture."`
    - *Standalone reels:* `"Save this so you don't lose this scripture."`
  - **~95% – 100% (Final 2–3s) | Sign-off & Loop Hook:**
    `"Follow for more secrets hidden in Scripture."` (or seamless loop back to the opening hook).
  - **Zero Baked-in Ads Invariant:** NEVER hardcode `"If this blew your mind..."` or any book/merch ads into the core reel narration script, voiceover audio, or video render. The core reel is ALWAYS rendered and saved clean (`<reel_name>_clean.mp4`).

* **Modular Ad Outro Architecture (Post-Roll Detachable Layer):**
  - All books & sacred art merch promotion lives exclusively in external, standalone Ad Outro video clips (`C:\Projects\Adz-Video\ad_outro_*.mp4`), appended strictly AFTER the clean reel finishes (100%+).
  - **1. CHOSEN:** Choose between built-in variants or custom video clips in `C:\Projects\Adz-Video`:
    - *Ad 1 (`ad_outro_1.mp4`):* Bestselling Books Vol 1 & 2 on Amazon + Sacred Art & Merch on Etsy.
    - *Ad 2 (`ad_outro_2.mp4`):* Book 1 Focus (50 Old Testament Mysteries).
    - *Ad 3 (`ad_outro_3.mp4`):* Book 2 Focus (Controversial Prophecies from Genesis to Revelation).
    - *Custom Clips:* Any vertical 768x1344/1080x1920 video added to `C:\Projects\Adz-Video`.
  - **2. ATTACHED:** Attached onto any rendered clean reel via fast, lossless stream concatenation (`-c copy -movflags +faststart`) in ~0.5s without re-rendering video or synthesizing audio.
    - CLI: `python generate_reel.py --week X --reel Y --combine-ad --ads [1|2|3|<filename>]` (or `--all` for entire week).
    - UI: Select ad in KCT Studio Ad Manager modal and click "Attach Ad".
  - **3. REMOVED:** Stripped/detached instantly in ~0.05s, restoring the pristine clean master video (`<reel_name>_clean.mp4` -> `<reel_name>_final_reel.mp4`).
    - CLI: `python generate_reel.py --week X --reel Y --remove-ad` (or `--all` for entire week).
    - UI: Click "Remove Ad" / toggle off in KCT Studio Ad Manager modal.
  - **State Persistence:** The reel's `metadata.json` tracks whether an ad is currently attached (`"ad_outro": {"attached": true/false, "filename": ...}`).

* **Prioritize Shares & Saves Over Likes:** Meta (Instagram/Facebook) and TikTok algorithms weigh **Shares 5x higher than Likes** when calculating viral distribution. Saves signal high-authority study and reference utility.
  - Frame CTAs around viewer value: *"Save this so you don't lose this scripture"* or *"Share this with someone who needs to hear this."*
  - Avoid weak, passive calls asking only for "likes".
* **No Early Begging:** NEVER ask for engagement or follows in the first 60 seconds (or before the 80% mark). Viewers must receive substantial theological revelation before any ask.
* **Comment & Store Links:** Direct viewers to the verified pinned comment for books and merchandise; never clutter the main video intro or description with external URLs.

## 3. Niche Depth & Content Packaging
* **Laser-Focused Niche:** Focus exclusively on deep biblical history, ancient manuscripts (Dead Sea Scrolls, Enoch, Qumran), and scriptural mysteries. Do not dilute the topic pool.
* **Value-Driven Titles:** Titles must make a singular, clear, high-curiosity promise (<= 100 characters, no forbidden characters like `<` or `>`).
* **Thumbnail Alignment:** FLUX image generation prompts must visually embody the dramatic core question of the title without graphic gore or sensationalist clickbait.

## 4. Platform Compliance & Audio Safety
* **AI Transparency:** Always ensure YouTube's `containsSyntheticMedia: True` flag is enabled for uploads featuring FLUX visuals or cloned voiceover.
* **URL Sanitization:** Video descriptions must remain clean and URL-free. All external URLs (Amazon, Etsy) reside strictly in the first pinned comment.
* **Royalty-Free Audio:** Ensure Demucs stem extraction sources exclusively from licensed or royalty-free audio tracks to prevent automated Content ID claims.

## 5. Weekly Folder Layout (Several Reels a Day)
* **Reel folders:** `W06/reels/<day>_<n>_<name>/`. `day` is `mon`..`sun`, and `n` is the reel's place in that day (`mon_1_why_god_rejected_cains_fruit`, `mon_2_abels_lamb_first_blood`, `tue_1_...`). The default is 2 a day, and a 3rd (`mon_3_...`) can be added. Never name new reel folders by number (`01_...`).
* **Posting time:** slot `n` posts at the project's `reel_posting_times[n-1]` (07:30, 17:30, 20:30 by default). A reel's `metadata.json` can pin `"post_time"`.
* **Reel metadata:** every new reel's `metadata.json` carries `"global_episode"` (its "Bible Secrets #NNN"). If it's missing, the generator assigns the next free number on the first render and saves it.
* **Stories name their reel by key:** `"reel": "tue_1"` in the story's `metadata.json` (not only `reel_num`), so adding a reel to a day never shifts a story onto another reel.
* **Week metadata:** each entry in `metadata.json` `"reels"` has `"num"`, `"day"` and `"folder"` (the folder name).

## 6. Weekly Package Standard (W03 Onward)
* **Every week:** the documentary (long-form episodes), 10 reels (2 a day, Mon–Fri), and 15 stories (3 a day). W03 is the reference week.
* **One narrative:** every reel and story must come from the week's documentary. Each reel takes one step of the documentary's argument (a chapter, a key verse, a Hebrew word, the Christological key) and sets `"supports_long_form"` to the episode folder it draws on. No generic, stand-alone reels or stories. When a week still has off-topic ones (W11–W60 do), replace them before that week is produced.
* **The day's arc:** `<day>_1` (07:30) opens the day's theme and `<day>_2` (17:30) takes it one step further. Across the week, the reels follow the documentary's order and end on Christ (Friday's 2nd reel carries the Christological key).
* **Story slots:** 08:00 follows `<day>_1` (`"final_cta": "NEW REEL ON OUR PAGE"`). 13:00 deepens `<day>_1` and points to the documentary (default end card). 20:00 follows `<day>_2` (`"final_cta": "NEW REEL ON OUR PAGE"`). Each story's `metadata.json` carries `"day"`, `"slot"`, `"post_time"` and `"reel"` (the calendar keeps a story on its day).
* **Reel visuals:** reels are narration-timed like the long-form: `generate_reel.py` cuts the narration into at most 20 scenes (fewer when it has fewer beats) in the reel's `scene_plan.json`, Claude Code/Gemini write each scene's prompt from its words, and each picture shows while its words are heard. A reel's `scenes.json` (`{"prompts": [...]}`), if present, is passed to the writer as picture ideas. Reels rendered earlier (`images/reelNN_dyn_*.png`) keep their pictures unless rendered with `--replan`. No text or lettering in prompts, no gore.
* **Reel length:** under 2:00 at the narration pace, i.e. about 210–240 words including the closing CTA ("Watch the full episode on our channel, and save this so you don't lose this scripture. Follow for more secrets hidden in Scripture.").
* **Accuracy:** quote Scripture (KJV wording unless the documentary uses another), and attribute rabbinic and historical claims only as far as the sources support. When unsure, say "the rabbis debated" rather than naming who said what.

## 7. Long-Form Pictures Follow the Narration
* **Voice first:** `generate_video.py` records the narration, then writes `scene_plan.json` in the episode folder: scenes of about 20 s cut at sentence ends, each with its `start`/`end` and the exact `text` spoken. It stops (exit code 3, "Voice Ready • N Scene Prompts Needed" in KCT Studio) until every scene has a `"prompt"`.
* **Automatic prompts:** after the voice, Claude Code and/or Gemini CLI write the prompts headless (order set by "Scene prompts" in KCT Studio) and the render continues; it pauses only when neither is signed in or the setting is "Pause for me". Never write "cherub" in a prompt (FLUX draws baby angels); use "towering angelic guardian".
* **Planning ahead:** scenes and prompts can be made before the voice ("Plan scenes" / `--plan-only`, then "Draw pictures" / `--images-only`). The recording re-times each scene to its first spoken word, keeping its prompt and picture.
* **House look:** dark, low-key scenes with deep black shadows lit by warm divine gold, in amber and gold tones (the W03 ep2 placeholder render). The generator adds it around every prompt; never ask for bright daylight, white or pastel settings, blue skies or saturated colors. A scene can reuse an existing picture with `"image"` (path relative to the episode folder) in `scene_plan.json`.
* **Writing the prompts:** one FLUX prompt per scene that shows what that scene's `text` says: the people, place and action named in it, in narration order. No text or lettering, no gore. Change only `"prompt"`; the next render draws the pictures and times each one to its words.
* **Script length:** 28 minutes is about 4,100 narration words at the long-form pace (145–150 wpm). Keep parentheses and square brackets out of narration lines (the generator strips them); put sources after a `SOURCES` line, which is never narrated.

