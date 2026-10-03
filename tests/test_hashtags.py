import unittest

import tests  # noqa: F401  (blocks network before core modules load)
from core.hashtags import find_hashtags, normalize_tags, strip_hashtags
from core.social_dispatcher import SocialDispatcher as SD


def many_tags(n):
    return " ".join(f"#Tag{chr(65 + i)}" for i in range(n))


class HashtagParsingTests(unittest.TestCase):
    def test_numbers_are_not_hashtags(self):
        self.assertEqual(find_hashtags("Part #2 of Bible Secrets #78 #Genesis"), ["#Genesis"])

    def test_code_url_fragments_and_entities_are_not_hashtags(self):
        self.assertEqual(find_hashtags("Learn C# at example.com/page#Intro or /#/route &#39;"), [])

    def test_inline_hashtag_keeps_its_word(self):
        text, tags = strip_hashtags("Join our #BibleStudy tonight.\n#Faith #Hope")
        self.assertEqual(text, "Join our BibleStudy tonight.")
        self.assertEqual(tags, ["#BibleStudy", "#Faith", "#Hope"])

    def test_trailing_tags_on_a_text_line_are_removed(self):
        text, tags = strip_hashtags("Watch now! #Faith #Hope")
        self.assertEqual(text, "Watch now!")
        self.assertEqual(tags, ["#Faith", "#Hope"])


class HashtagNormalizingTests(unittest.TestCase):
    def test_platform_caps(self):
        self.assertEqual(len(normalize_tags(many_tags(20), "youtube").split()), 15)
        self.assertEqual(len(normalize_tags(many_tags(20), "instagram").split()), 5)
        self.assertEqual(len(normalize_tags(many_tags(20), "threads").split()), 1)
        self.assertEqual(len(normalize_tags(many_tags(20), "x").split()), 2)

    def test_dedupes_case_insensitively_and_filters_sensitive_on_short_form_feeds(self):
        self.assertEqual(normalize_tags("#Bible #bible #SpiritualWarfare #Faith", "instagram"), "#Bible #Faith")
        # Facebook and YouTube keep the post's own tags as written
        self.assertEqual(normalize_tags("#Bible #bible #SpiritualWarfare #Faith", "facebook"), "#Bible #SpiritualWarfare #Faith")

    def test_multi_word_and_verse_tags_become_single_hashtags(self):
        self.assertEqual(
            normalize_tags(["#Genesis 1:1", "#Pre-CosmicFall", "Bara vs Asah", "#Colossians1:16"], "facebook"),
            "#Genesis1 #PreCosmicFall #BaraVsAsah #Colossians1"
        )

    def test_list_tags_with_spaces_become_single_tags(self):
        self.assertEqual(normalize_tags(["Bible Study", "#Faith", "2"], "facebook"), "#BibleStudy #Faith")

    def test_brand_tags_only_when_every_tag_was_filtered(self):
        self.assertEqual(normalize_tags("", "youtube"), "")
        self.assertIn("#BibleSecrets", normalize_tags("#Lucifer #Satan", "instagram"))


class CaptionSanitizerTests(unittest.TestCase):
    def test_youtube_keeps_episode_numbers_in_text(self):
        out = SD.sanitize_urls_for_youtube("Bible Secrets #78: Part #2 of the series.\n\n#Genesis #Faith")
        self.assertIn("Bible Secrets #78: Part #2 of the series.", out)
        self.assertTrue(out.endswith("#Genesis #Faith"))

    def test_youtube_keeps_more_than_five_tags(self):
        out = SD.sanitize_urls_for_youtube("Body\n\n" + many_tags(8))
        self.assertEqual(len(find_hashtags(out)), 8)

    def test_no_brand_tags_added_to_untagged_text(self):
        self.assertEqual(SD.sanitize_urls_for_youtube("Just a description."), "Just a description.")

    def test_threads_keeps_one_tag(self):
        out = SD.sanitize_caption_for_threads("Short post.\n\n#Faith #Hope #Love")
        self.assertEqual(out, "Short post.\n\n#Faith")

    def test_facebook_puts_explicit_tags_first(self):
        out = SD.sanitize_caption_for_facebook("Body text.\n\n#Hope", hashtags="#Faith")
        self.assertTrue(out.endswith("#Faith #Hope"))

    def test_sanitizers_are_idempotent(self):
        raw = "Hook line\nBody with #Genesis inside.\n\n#Faith #Hope #Genesis"
        for fn in (SD.sanitize_urls_for_youtube, SD.sanitize_urls_for_instagram,
                   SD.sanitize_caption_for_tiktok, SD.sanitize_caption_for_facebook):
            with self.subTest(fn=fn.__name__):
                once = fn(raw)
                self.assertEqual(fn(once), once)


if __name__ == "__main__":
    unittest.main()
