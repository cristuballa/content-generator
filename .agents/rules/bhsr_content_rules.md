# BHSR Content & Video Generation Guidelines

These rules apply whenever drafting scripts, generating episode metadata, or creating 16:9 documentary videos and vertical Reels/Shorts for Bible Hidden Secrets Revealed (BHSR).

## 1. Hook & First 15 Seconds (Zero Fluff)
* **Immediate Delivery:** Open immediately with the core curiosity hook or central mystery (e.g., *"What happened in the unseen realm before Genesis 1:1?"*).
* **No Intros:** Do NOT include animated channel logos, music stings, or creator greetings (*"Welcome back to the channel"* or *"Today we are going to talk about..."*) in the first 15 seconds.
* **Fulfill the Promise:** The opening lines must directly validate the question posed in the video title and thumbnail.

## 2. Retention & Call-to-Action (CTA) Placement
* **No Early Begging:** NEVER ask for likes, subscribes, or notifications in the first 60 seconds (or before the 70% mark). Viewers must receive substantial value before any engagement ask.
* **Natural Mid-to-Late CTA:** Place a subtle, value-driven subscription prompt only after delivering a major scriptural or historical revelation (around 75%–80% through the script).
* **Comment & Store Links:** Direct viewers to the verified pinned comment for books and merchandise; never clutter the main video intro with store announcements.

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
* **Reel length:** under 2:00 at the narration pace, i.e. about 235–255 words including the closing CTA ("Watch the full episode on our channel." + the books line + "Follow for more secrets hidden in Scripture.").
* **Accuracy:** quote Scripture (KJV wording unless the documentary uses another), and attribute rabbinic and historical claims only as far as the sources support. When unsure, say "the rabbis debated" rather than naming who said what.

