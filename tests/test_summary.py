"""The numbers in the README must come from the committed data."""
import csv, pathlib, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestData(unittest.TestCase):
    def setUp(self):
        with open(ROOT / "data" / "profiles.csv", encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))

    def test_sample_size(self):
        self.assertEqual(len(self.rows), 62)

    def test_readme_counts(self):
        with_readme = sum(1 for r in self.rows if r["has_profile_readme"] == "true")
        self.assertEqual(with_readme, 30)
        self.assertEqual(len(self.rows) - with_readme, 32)

    def test_peer_accounts_are_pseudonymised(self):
        peers = [r for r in self.rows if r["source_list"] in ("design-peer", "seo-peer")]
        self.assertTrue(all(r["login"].startswith(("design-peer-", "seo-peer-")) for r in peers))


if __name__ == "__main__":
    unittest.main()
