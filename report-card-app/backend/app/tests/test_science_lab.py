"""No pytest in this repo yet (see requirements.txt) — plain stdlib
unittest + unittest.mock keeps this dependency-free. Run with:
    venv\\Scripts\\python -m unittest app.tests.test_science_lab -v
Mocks every HTTP call — never touches the real Smart Science Lab service."""
import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.integrations import science_lab

_INDEX = {
    "catalogs": [
        {"class": 10, "subject": "Physical Science", "curriculum": "NCERT", "url": "shared/catalog.physical-science-10.json"},
    ]
}

_CATALOG = {
    "class": 10,
    "subject": "Physical Science",
    "curriculum": "NCERT",
    "base_url": "https://interactive-labs.onrender.com",
    "chapters": [
        {
            "chapter": 1, "title": "Chemical Reactions and Equations", "topic_group": "Chemistry",
            "emoji": "⚗️",
            "overview_path": "Lesson-01-Chemical-Reactions/index.html",
            "lab": {"path": "Lesson-01-Chemical-Reactions/lab.html", "experiments": None},
            "games": {"path": "Lesson-01-Chemical-Reactions/games.html", "list": [
                {"id": "typ", "title": "Reaction Type"}, {"id": "bal", "title": "Balance It"},
            ]},
        },
        {
            "chapter": 9, "title": "Light – Reflection and Refraction", "topic_group": "Physics",
            "emoji": "\U0001f526",
            "overview_path": "Lesson-09-Light/index.html",
            "lab": {"path": "Lesson-09-Light/lab.html", "experiments": [
                {"id": "pickK", "title": "Concave mirror images"},
                {"id": "pickV", "title": "Convex lens images"},
                {"id": "pickS", "title": "Refraction through a glass slab"},
            ]},
            "games": {"path": "Lesson-09-Light/games.html", "list": [
                {"id": "mir", "title": "Mirror World"}, {"id": "len", "title": "Lens World"},
                {"id": "img", "title": "Image Finder"}, {"id": "frm", "title": "Formula Solver"},
                {"id": "bend", "title": "Bend It"},
            ]},
        },
    ],
}


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


class ScienceLabTests(unittest.TestCase):
    def setUp(self):
        # Module-level cache would otherwise leak between tests.
        science_lab._cache["index"] = None
        science_lab._cache["catalogs"] = {}
        science_lab._cache["fetched_at"] = 0.0

    @patch("app.integrations.science_lab.httpx.get")
    def test_get_chapter_activities_builds_correct_urls(self, mock_get):
        mock_get.side_effect = [_mock_response(_INDEX), _mock_response(_CATALOG)]
        result = science_lab.get_chapter_activities(9)
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Light – Reflection and Refraction")
        self.assertEqual(len(result["lab"]["experiments"]), 3)
        self.assertEqual(len(result["games"]["list"]), 5)
        self.assertEqual(
            result["games"]["list"][1]["url"],
            "https://interactive-labs.onrender.com/Lesson-09-Light/games.html?g=len",
        )

    @patch("app.integrations.science_lab.httpx.get")
    def test_chapter_not_in_catalog_returns_none(self, mock_get):
        mock_get.side_effect = [_mock_response(_INDEX), _mock_response(_CATALOG)]
        self.assertIsNone(science_lab.get_chapter_activities(5))  # Biology, not in catalog

    @patch("app.integrations.science_lab.httpx.get")
    def test_find_by_title_is_case_and_dash_insensitive(self, mock_get):
        mock_get.side_effect = [_mock_response(_INDEX), _mock_response(_CATALOG)]
        a = science_lab.find_chapter_by_title("Light – Reflection and Refraction")
        mock_get.side_effect = None  # second call should hit the cache, not fetch again
        b = science_lab.find_chapter_by_title("light - reflection and refraction")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(a["chapter"], 9)
        self.assertEqual(b["chapter"], 9)

    @patch("app.integrations.science_lab.httpx.get")
    def test_this_apps_own_chapter_numbering_does_not_leak_in(self, mock_get):
        # report-card-app's own syllabus_chapter has chapter_no=1 == "Heat" —
        # proving title-matching (not number-matching) is what's actually used.
        mock_get.side_effect = [_mock_response(_INDEX), _mock_response(_CATALOG)]
        self.assertIsNone(science_lab.find_chapter_by_title("Heat"))

    @patch("app.integrations.science_lab.httpx.get")
    def test_fetch_failure_degrades_to_none(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("boom")
        self.assertIsNone(science_lab.get_chapter_activities(9))
        self.assertIsNone(science_lab.find_chapter_by_title("Light – Reflection and Refraction"))


if __name__ == "__main__":
    unittest.main()
