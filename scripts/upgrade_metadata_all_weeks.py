"""
=============================================================================
METADATA UPGRADE ENGINE: MULTI-PLATFORM GOLD STANDARD BENCHMARK
Standard: Image 2 Facebook & Multi-Platform Benchmark
Platforms: YouTube (Shorts & Long-Form), Facebook, Instagram, TikTok, X (Twitter)
=============================================================================
"""

import os
import sys
import re
import json
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Adjust paths
PIPELINE_ROOT = Path(r"c:\Projects\AI-Content-Generation-Pipeline")
BHSR_ROOT = Path(r"C:\Projects\BHSR")
sys.path.insert(0, str(PIPELINE_ROOT))

from core.social_dispatcher import social_dispatcher, DEFAULT_BHRS_MERCH_BLOCK

# High-impact curated metadata for Week 01 Reels
W01_CURATED_METADATA = {
    1: {
        "title": "What Did God Do BEFORE Genesis 1:1? — The Secret Pre-Creation Council",
        "hook_text": "WHAT WAS GOD DOING FOR ETERNITY BEFORE GENESIS 1:1?",
        "scriptures": "Job 38:4-7, John 17:24, Colossians 1:16-17, Revelation 13:8",
        "body_narrative": (
            "What was God doing for eternity BEFORE Genesis 1:1? Most people assume God sat in solitary silence, "
            "alone in an infinite void waiting to create. But Jesus shattered that myth in John 17:24: 'Father, You loved Me "
            "before the foundation of the world.' Before a single galaxy spun into existence, the Father, Son, and Holy Spirit "
            "shared uncreated, infinite love. Creation was never born out of divine loneliness—it was the explosive overflow "
            "of eternal triune love.\n\n"
            "Job 38 reveals an astonishing mystery: when God laid the earth's foundations, the Morning Stars sang together "
            "and all the sons of God (Bene Elohim) shouted for joy! Heaven was already ringing with anthems of praise long before "
            "Adam drew his first breath in Eden. Colossians 1:16 confirms that all things were created THROUGH Christ and FOR Christ. "
            "You were not an afterthought—your redemption was prepared before the foundation of the world."
        ),
        "tags": [
            "BibleSecrets", "ScriptureUncovered", "Genesis", "Job38", "BeforeGenesis",
            "DivineCouncil", "BeneElohim", "JesusChrist", "Theology", "AncientHebrew",
            "Creation", "ProphecyFulfilled", "BiblicalTruth", "Faith"
        ]
    },
    2: {
        "title": "The Cross Hidden in the Very First Hebrew Word — Bereshit Decoded",
        "hook_text": "THE ENTIRE GOSPEL IS HIDDEN IN THE FIRST WORD OF GENESIS",
        "scriptures": "Genesis 1:1, Psalm 2:12, John 1:1, Revelation 13:8",
        "body_narrative": (
            "The entire Gospel of Jesus Christ is stamped into the very first Hebrew word of the Bible: BERESHIT (In the beginning). "
            "In ancient Paleo-Hebrew, every letter was an active living pictograph carrying prophetic meaning.\n\n"
            "• Bet (House / Temple) + Resh (Firstborn Son / Prince) = BAR, the Hebrew and Aramaic word for SON (Psalm 2:12).\n"
            "• Aleph (Ox Head) = God, divine power, and majesty.\n"
            "• Shin (Teeth) = To crush, destroy, or consume.\n"
            "• Yod (Hand) = Outstretched hand of divine action.\n"
            "• Tav (Two crossed sticks) = A COVENANT SIGN or THE CROSS!\n\n"
            "Read all six ancient pictographs together in divine sequence: 'The Son of God, destroyed by His own hands, on the Cross!' "
            "Before God framed human history, Calvary was already woven into the first syllable of Genesis. Revelation 13:8 calls Jesus "
            "the Lamb slain before the foundation of the world."
        ),
        "tags": [
            "BibleSecrets", "ScriptureUncovered", "Bereshit", "PaleoHebrew", "AncientHebrew",
            "TheCross", "JesusInTheOldTestament", "Gospel", "ProphecyFulfilled", "BibleStudy",
            "MessianicProphecy", "Genesis1", "BiblicalArchaeology", "BiblicalTruth"
        ]
    },
    3: {
        "title": "Who Were the 'Morning Stars' Who Sang at Creation? — Job 38 Revealed",
        "hook_text": "DID ANGELS WITNESS THE CREATION OF PLANET EARTH?",
        "scriptures": "Job 38:4-7, Luke 15:10, Revelation 4:11, Psalm 89:5-7",
        "body_narrative": (
            "Did angels witness the creation of Planet Earth? Not as silent bystanders—but as a roaring, celebrating cosmic audience! "
            "In Job 38, when the Almighty answered Job from the whirlwind, He asked: 'Where were you when I laid the foundations "
            "of the earth? When the morning stars sang together, and all the sons of God shouted for joy?'\n\n"
            "The Hebrew phrase is Bene Elohim—the heavenly divine council. These were personal, conscious celestial beings who watched "
            "mountains rise and oceans carve their boundaries. They did not help God create; they erupted in thunderous worship AS He created!\n\n"
            "Here is the profound takeaway: if the angelic host celebrated when the physical earth was framed, how much greater is their joy "
            "over your salvation? Luke 15:10 tells us heaven rejoices over one sinner who repents. The celebration that began at creation continues today."
        ),
        "tags": [
            "BibleSecrets", "ScriptureUncovered", "Job38", "MorningStars", "BeneElohim",
            "AngelsInTheBible", "DivineCouncil", "AngelicWorship", "Creation", "AncientScripture",
            "BiblicalTruth", "Theology", "Worship", "ChristianReels"
        ]
    },
    4: {
        "title": "Why the Apostle John Re-Wrote Genesis 1 — The Eternal Logos Unveiled",
        "hook_text": "WHY DID JOHN OPEN HIS GOSPEL WITH THE WORDS OF GENESIS 1?",
        "scriptures": "John 1:1-14, Genesis 1:1-3, Psalm 33:6, Colossians 1:16-17",
        "body_narrative": (
            "Why did the Apostle John open his Gospel with the exact same opening words as Genesis 1:1? 'In the beginning was the Word, "
            "and the Word was with God, and the Word was God.' Moses recorded the EVENT of creation, but John reveals the PERSON who was speaking!\n\n"
            "In Greek thought, the Logos was an impersonal cosmic force. In Hebrew theology, the Dabar Yahweh (Word of the LORD) was the dynamic "
            "power that commanded reality. John takes both concepts and delivers an explosive revelation: The Logos is not an abstract philosophy. "
            "The Logos is a Person—and the Word became flesh!\n\n"
            "Every time God spoke 'Let there be light' in Genesis 1, Jesus was the uncreated Voice commanding light out of darkness. "
            "John 1:3 declares: 'Without Him was not anything made that was made.' Jesus did not start in Bethlehem—He is the Architect of eternity."
        ),
        "tags": [
            "BibleSecrets", "ScriptureUncovered", "John1", "Logos", "Genesis1",
            "PreExistentChrist", "Trinity", "WordOfGod", "JesusChrist", "Theology",
            "DeepBibleStudy", "ScriptureDeepDive", "BiblicalTruth", "Christology"
        ]
    },
    5: {
        "title": "The Pre-Cosmic Fall of Lucifer — Pride Before the Dust of Earth",
        "hook_text": "WHEN DID LUCIFER ACTUALLY FALL? (BEFORE HUMAN HISTORY)",
        "scriptures": "Ezekiel 28:12-19, Isaiah 14:12-15, Luke 10:18, Revelation 12:7-9",
        "body_narrative": (
            "When did Lucifer actually fall? Most people assume Satan's rebellion began in the Garden of Eden. But Scripture reveals his disqualification "
            "happened long before the first human drew breath.\n\n"
            "In Ezekiel 28, God speaks of the covering cherub stationed on the holy mountain of God: 'You were the signet of perfection, full of wisdom "
            "and perfect in beauty. You were blameless in your ways from the day you were created, till iniquity was found in you.' "
            "Isaiah 14 records the five fatal 'I will' declarations: 'I will ascend into heaven, I will exalt my throne above the stars of God... "
            "I will be like the Most High.'\n\n"
            "The first sin in creation was not murder or theft—it was pride. Lucifer was disqualified from his station at the throne. "
            "Jesus confirmed in Luke 10:18: 'I saw Satan fall like lightning from heaven.' The false morning star was cast down, clearing the stage "
            "for the True and Eternal Morning Star: Jesus Christ!"
        ),
        "tags": [
            "BibleSecrets", "ScriptureUncovered", "Lucifer", "Ezekiel28", "Isaiah14",
            "SpiritualWarfare", "FallOfSatan", "AngelsAndDemons", "BeforeGenesis", "Theology",
            "DeepBibleStudy", "ProphecyFulfilled", "BiblicalTruth", "ChristianFaith"
        ]
    }
}

# Long-Form Episode 1 Metadata
W01_LONG_FORM_METADATA = {
    "title": "What Happened BEFORE Genesis 1:1? The Secret Pre-Creation War [Full Documentary]",
    "hook_text": "WHAT HAPPENED BEFORE THE FOUNDATION OF THE WORLD?",
    "scriptures": "Job 38:4-7, Proverbs 8:22-31, John 1:1-14, Colossians 1:16-17, Ezekiel 28:12-19, Revelation 13:8",
    "body_narrative": (
        "The Bible opens at Genesis 1:1... but what happened BEFORE the foundation of the world? "
        "In this 32-minute deep-dive documentary, we explore the pre-cosmic divine council of God, the songs of the Morning Stars "
        "in Job 38, the eternal generation of the Logos in John 1, the prophetic code hidden in the Hebrew word Bereshit, "
        "and the disqualification of the anointed covering cherub before the dust of earth was formed.\n\n"
        "TIMESTAMPS / CHAPTERS:\n"
        "00:00 - The Silence Before Creation\n"
        "04:15 - The Divine Council (Bene Elohim) in Job 38\n"
        "09:30 - The Eternal Wisdom of Proverbs 8\n"
        "14:45 - Bereshit: The Cross Concealed in the First Hebrew Word\n"
        "20:10 - Why Lucifer Desired the Cosmic Mountain (Ezekiel 28)\n"
        "25:30 - John 1: The Word That Preceded the Cosmos\n"
        "30:00 - Christ the Uncreated King: The Redemptive Climax"
    ),
    "tags": [
        "What Happened Before Genesis", "Genesis 1:1", "Divine Council", "Job 38 Morning Stars",
        "Pre-Cosmic Fall", "John 1 Logos", "Bereshit Paleo Hebrew", "Ancient Hebrew Secrets",
        "Lucifer Before Eden", "Ezekiel 28", "Colossians 1:16", "Bible Mysteries",
        "BiblicalArchaeology", "BibleSecrets", "FullDocumentary"
    ]
}


def upgrade_week_reels(week_num: int = 1):
    week_tag = f"W{week_num:02d}"
    print(f"\n{'='*74}")
    print(f"UPGRADING METADATA FOR WEEK {week_tag} TO PRODUCTION BENCHMARK STANDARD")
    print(f"{'='*74}")

    targets = [
        BHSR_ROOT / week_tag,
        PIPELINE_ROOT / week_tag
    ]

    for base_p in targets:
        if not base_p.exists():
            continue
        print(f"\n▶ Updating project folder: {base_p}")
        
        # 1. Update Long-Form Documentary Metadata
        lf_dir = base_p / "long_form"
        if lf_dir.exists():
            lf_data = W01_LONG_FORM_METADATA
            fb_cap = social_dispatcher.build_facebook_caption(
                hook=lf_data["title"],
                body=lf_data["body_narrative"],
                hashtags=" ".join([f"#{t.replace(' ', '')}" for t in lf_data["tags"]])
            )
            yt_desc = social_dispatcher.build_youtube_description(
                hook=lf_data["title"],
                body=lf_data["body_narrative"],
                hashtags=" ".join([f"#{t.replace(' ', '')}" for t in lf_data["tags"]])
            )
            ig_cap = social_dispatcher.build_instagram_caption(
                hook=lf_data["title"],
                body=lf_data["body_narrative"],
                hashtags=" ".join([f"#{t.replace(' ', '')}" for t in lf_data["tags"]])
            )
            tt_cap = social_dispatcher.build_tiktok_caption(
                hook=lf_data["title"],
                body=lf_data["body_narrative"],
                hashtags=" ".join([f"#{t.replace(' ', '')}" for t in lf_data["tags"]])
            )
            x_post = social_dispatcher.build_x_post(
                hook=lf_data["title"],
                body=lf_data["body_narrative"],
                url="https://youtube.com/@BibleHiddenSecrets",
                hashtags=" ".join([f"#{t.replace(' ', '')}" for t in lf_data["tags"]])
            )

            for meta_name in ["episode_metadata.json", "metadata.json"]:
                meta_file = lf_dir / meta_name
                meta_json = {}
                if meta_file.exists():
                    try: meta_json = json.loads(meta_file.read_text(encoding="utf-8"))
                    except Exception: pass
                
                meta_json.update({
                    "title": lf_data["title"],
                    "hook": lf_data["hook_text"],
                    "description": lf_data["body_narrative"],
                    "scriptures": lf_data["scriptures"],
                    "tags": lf_data["tags"],
                    "hashtags": [f"#{t.replace(' ', '')}" for t in lf_data["tags"]],
                    "merch_block": DEFAULT_BHRS_MERCH_BLOCK,
                    "facebook_caption": fb_cap,
                    "youtube_description": yt_desc,
                    "instagram_caption": ig_cap,
                    "tiktok_caption": tt_cap,
                    "x_post": x_post
                })
                meta_file.write_text(json.dumps(meta_json, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  [SUCCESS] Updated {meta_file.name} for Long-Form")

        # 2. Update All 5 Reels
        reels_dir = base_p / "reels"
        if reels_dir.exists():
            subdirs = sorted([d for d in reels_dir.iterdir() if d.is_dir() and d.name.lower() not in ("temp", "temp_slides")])
            for idx, r_dir in enumerate(subdirs[:5]):
                reel_num = idx + 1
                cur_data = W01_CURATED_METADATA.get(reel_num, {})
                if not cur_data:
                    continue

                tags = cur_data.get("tags", [])
                ht_str = " ".join([f"#{t}" for t in tags])

                fb_cap = social_dispatcher.build_facebook_caption(
                    hook=cur_data["title"],
                    body=cur_data["body_narrative"],
                    hashtags=ht_str
                )
                yt_desc = social_dispatcher.build_youtube_description(
                    hook=cur_data["title"],
                    body=cur_data["body_narrative"],
                    hashtags=ht_str
                )
                ig_cap = social_dispatcher.build_instagram_caption(
                    hook=cur_data["title"],
                    body=cur_data["body_narrative"],
                    hashtags=ht_str
                )
                tt_cap = social_dispatcher.build_tiktok_caption(
                    hook=cur_data["title"],
                    body=cur_data["body_narrative"],
                    hashtags=ht_str
                )
                x_post = social_dispatcher.build_x_post(
                    hook=cur_data["title"],
                    body=cur_data["body_narrative"],
                    url="https://youtube.com/@BibleHiddenSecrets",
                    hashtags=ht_str
                )

                meta_p = r_dir / "metadata.json"
                r_meta = {}
                if meta_p.exists():
                    try: r_meta = json.loads(meta_p.read_text(encoding="utf-8"))
                    except Exception: pass

                r_meta.update({
                    "reel_id": f"REEL-{week_tag}.{reel_num}",
                    "week": week_num,
                    "reel_num": reel_num,
                    "title": cur_data["title"],
                    "hook": cur_data["hook_text"],
                    "hook_text": cur_data["hook_text"],
                    "scriptures": cur_data["scriptures"],
                    "description": cur_data["body_narrative"],
                    "caption": fb_cap,
                    "tags": tags,
                    "hashtags": [f"#{t}" for t in tags],
                    "merch_block": DEFAULT_BHRS_MERCH_BLOCK,
                    "facebook_caption": fb_cap,
                    "youtube_description": yt_desc,
                    "instagram_caption": ig_cap,
                    "tiktok_caption": tt_cap,
                    "x_post": x_post
                })

                meta_p.write_text(json.dumps(r_meta, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  [SUCCESS] Reel 0{reel_num} ({r_dir.name}) -> Upgraded metadata.json (FB: {len(fb_cap)}c, X: {len(x_post)}c)")

    print(f"\n{'='*74}")
    print(f"METADATA UPGRADE COMPLETE FOR WEEK {week_tag}")
    print(f"{'='*74}\n")

if __name__ == "__main__":
    upgrade_week_reels(1)
