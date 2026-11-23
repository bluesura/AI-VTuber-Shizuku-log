import unittest

from ocr_youtube_overlay import new_scroll_lines, timeline_events


def observation(pts, *texts, region=0, mode="replace"):
    return {"pts_ms": pts, "region": region, "mode": mode, "frame": f"frames/{pts}.png",
            "lines": [{"text": text, "box": [5, 20 * n, 100, 20 * n + 15], "score": 0.95}
                      for n, text in enumerate(texts)]}


class OverlayTimelineTests(unittest.TestCase):
    def test_keeps_single_character_changes_and_reappearance(self):
        observations = [observation(0, "パカポー"), observation(250, "パカポー"),
                        observation(500, "パカボー"), observation(750),
                        observation(1000, "パカボー")]
        self.assertEqual([(pts, text) for pts, text, *_ in timeline_events(observations)],
                         [(0, "パカポー"), (500, "パカボー"), (1000, "パカボー")])

    def test_progressive_caption_uses_frame_with_complete_text(self):
        observations = [observation(0, "パン"), observation(250, "パンカ"),
                        observation(500, "パンカパンパカポず"), observation(750)]
        self.assertEqual(list(timeline_events(observations)),
                         [(500, "パンカパンパカポず", 0.95, "frames/500.png", False)])

    def test_scroll_retains_only_new_positions_in_continuous_display(self):
        previous = observation(0, "最初", "もう一回", mode="scroll")["lines"]
        current = observation(250, "もう一回", "もう一回", mode="scroll")["lines"]
        self.assertEqual(new_scroll_lines(previous, current), current[1:])

    def test_new_layout_starts_a_separate_observation(self):
        rows = [observation(0, "おはよう"), observation(500, "おはよう", region=1)]
        self.assertEqual([pts for pts, *_ in timeline_events(rows)], [0, 500])

    def test_same_image_with_ocr_disagreement_is_marked(self):
        rows = [{**observation(pts, text), "display": 1} for pts, text in
                [(0, "大三元"), (250, "大二元"), (500, "大三元")]]
        self.assertEqual(list(timeline_events(rows)), [(0, "大三元", 0.95, "frames/0.png", True)])

    def test_same_image_breaks_vote_ties_by_score(self):
        first = {**observation(0, "うっぴっ…びぴ"), "display": 1}
        second = {**observation(250, "うっぴっ…ぴ"), "display": 1}
        second["lines"][0]["score"] = 0.98
        self.assertEqual(list(timeline_events([first, second])),
                         [(250, "うっぴっ…ぴ", 0.98, "frames/250.png", True)])


if __name__ == "__main__":
    unittest.main()
