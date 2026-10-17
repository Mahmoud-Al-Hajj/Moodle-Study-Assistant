"""Tests for Stages 1-4 against a fake Moodle (tests/fake_moodle.py).

    .venv\\Scripts\\python tests\\run_tests.py            # everything (one test opens a browser window)
    set SKIP_HEADED=1 & .venv\\Scripts\\python tests\\run_tests.py   # skip the visible-browser login test

Each test copies the project scripts into a throwaway folder, so your real
.env, auth/ and data/ are never touched. Rerun after any change to
moodle_selectors.py or scrape.py.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fake_moodle  # noqa: E402
from test_extract import TestExtract  # noqa: E402,F401  (Stage 4 tests run with the rest)

PROJECT = Path(__file__).resolve().parents[1]
SCRIPTS = ["common.py", "moodle_selectors.py", "login.py", "check_session.py", "scrape.py", "downloader.py"]

SERVER = None
SITE = ""


def setUpModule():
    global SERVER, SITE
    SERVER, SITE = fake_moodle.start()


def tearDownModule():
    SERVER.shutdown()


class Workspace(unittest.TestCase):
    """A throwaway copy of the project with its own .env, auth/ and data/."""

    def setUp(self):
        fake_moodle.Handler.auto_login = False
        fake_moodle.Handler.expire_files = set()
        self.dir = Path(tempfile.mkdtemp(prefix="moodle-test-"))
        for name in SCRIPTS:
            shutil.copy(PROJECT / name, self.dir / name)
        (self.dir / ".env").write_text(f"MOODLE_URL={SITE}\nCOURSE_ID=100\n", encoding="utf-8")
        self.set_cookie("good")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def set_cookie(self, value: str | None):
        state = self.dir / "auth" / "state.json"
        if value is None:
            state.unlink(missing_ok=True)
            return
        state.parent.mkdir(exist_ok=True)
        state.write_text(json.dumps({"cookies": [{
            "name": "MoodleSession", "value": value, "domain": "127.0.0.1", "path": "/",
            "expires": -1, "httpOnly": True, "secure": False, "sameSite": "Lax"}], "origins": []}))

    def run_script(self, script: str, *args: str, stdin: str | None = None) -> tuple[int, str]:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run([sys.executable, script, *args], cwd=self.dir, env=env, input=stdin,
                              capture_output=True, text=True, encoding="utf-8", timeout=180)
        out = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", out, "scripts must never print a stack trace")
        return proc.returncode, out

    def manifest(self, name: str = "manifest.json") -> dict:
        return json.loads((self.dir / "data" / name).read_text(encoding="utf-8"))

    def by_id(self, manifest: dict) -> dict:
        return {it["id"]: it for it in manifest["items"]}


class TestSession(Workspace):
    def test_valid_session(self):
        code, out = self.run_script("check_session.py")
        self.assertEqual(code, 0, out)
        self.assertIn("Session is valid", out)

    def test_expired_session(self):
        self.set_cookie("stale")
        code, out = self.run_script("check_session.py")
        self.assertEqual(code, 2, out)
        self.assertIn("NOT valid", out)
        self.assertIn("login.py", out)

    def test_guest_session_is_not_valid(self):
        self.set_cookie("guest")
        code, out = self.run_script("check_session.py")
        self.assertEqual(code, 2, out)

    def test_missing_session(self):
        self.set_cookie(None)
        for script in ("check_session.py", "scrape.py"):
            code, out = self.run_script(script)
            self.assertEqual(code, 2, out)
            self.assertIn("python login.py", out)

    def test_scrape_with_expired_session(self):
        self.set_cookie("stale")
        code, out = self.run_script("scrape.py", "--no-download")
        self.assertEqual(code, 2, out)
        self.assertIn("expired", out)
        self.assertFalse((self.dir / "data" / "manifest.json").exists())

    def test_missing_env(self):
        (self.dir / ".env").unlink()
        code, out = self.run_script("check_session.py")
        self.assertEqual(code, 1, out)
        self.assertIn(".env.example", out)

    @unittest.skipIf(os.environ.get("SKIP_HEADED"), "SKIP_HEADED is set")
    def test_interactive_login(self):
        """Opens a real browser window for ~10 s. The fake login page 'logs in' 3 s after loading."""
        self.set_cookie(None)
        fake_moodle.Handler.auto_login = True
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen([sys.executable, "login.py"], cwd=self.dir, env=env, text=True, encoding="utf-8",
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        proc.stdin.write("\n")      # Enter too early: still on the login page
        proc.stdin.flush()
        time.sleep(8)
        proc.stdin.write("\n")      # Enter after the dashboard loaded
        proc.stdin.flush()
        out, _ = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, out)
        self.assertIn("don't look logged in yet", out)
        self.assertIn("Session saved", out)
        self.assertNotIn("Traceback", out)
        state = json.loads((self.dir / "auth" / "state.json").read_text())
        self.assertTrue(any(c["name"] == "MoodleSession" and c["value"] == "good" for c in state["cookies"]))
        code, out = self.run_script("check_session.py")
        self.assertEqual(code, 0, out)


class TestScrape(Workspace):
    """Stage 2: crawl and manifest only (--no-download)."""

    def run_script(self, script, *args, **kw):
        if script == "scrape.py" and "--no-download" not in args:
            args = (*args, "--no-download")
        return super().run_script(script, *args, **kw)

    def test_boost_course(self):
        code, out = self.run_script("scrape.py")
        self.assertEqual(code, 0, out)
        m = self.manifest()
        self.assertEqual(m["course_name"], "Data Structures (CS201)")
        self.assertEqual(m["course_id"], "100")
        self.assertEqual([(s["section_number"], s["section_name"], s["item_count"]) for s in m["sections"]],
                         [(0, "General", 2), (1, "Week 1: Arrays / Lists?", 7), (2, "Week 2", 1),
                          (3, "Week 3 (empty)", 0)])
        items = self.by_id(m)
        self.assertEqual(len(m["items"]), 10)
        expected = {
            "cm:10": ("other", "forum", "Announcements"),
            "cm:11": ("resource", "resource", "Lecture 1 slides"),
            "cm:12": ("folder", "folder", "Lab files"),
            "cm:14": ("assign", "assign", "Homework 1"),
            "cm:15": ("other", "quiz", "Quiz 1"),
            "cm:17": ("page", "page", "Notes page"),
            "cm:18": ("url", "url", "Visualgo"),
        }
        for item_id, (typ, module, title) in expected.items():
            self.assertEqual((items[item_id]["type"], items[item_id]["module"], items[item_id]["title"]),
                             (typ, module, title), item_id)
        inline = sorted(it["title"] for it in m["items"] if it["module"] == "inline_file")
        self.assertEqual(inline, ["Reading 1", "Syllabus", "hw1.pdf"])
        self.assertTrue(all(it["type"] == "other" for it in m["items"] if it["module"] == "inline_file"))

        # The seven required fields plus id, module, note, on every item.
        fields = {"section_number", "section_name", "title", "type", "url", "local_path", "status", "id", "module",
                  "note", "files", "target_url"}
        for it in m["items"]:
            self.assertEqual(set(it), fields)
            self.assertEqual(it["local_path"], "")

        quiz = items["cm:15"]
        self.assertEqual(quiz["status"], "unavailable")
        self.assertEqual(quiz["url"], "")
        self.assertIn("Homework 1", quiz["note"])
        self.assertTrue(all(it["status"] == "pending" for it in m["items"] if it["id"] != "cm:15"))
        self.assertEqual(items["cm:17"]["section_number"], 1)  # subsection content belongs to the parent
        self.assertTrue(items["cm:11"]["url"].startswith(SITE + "/mod/resource/view.php"))

        # Cross-check reports the teacher-hidden item but does not add it.
        self.assertNotIn("cm:19", items)
        self.assertIn("Stealth handout", out)
        self.assertIn("NOT added", out)
        self.assertIn("Total items: 10", out)

    def test_throttled_requests(self):
        fake_moodle.Handler.requests.clear()
        start = time.monotonic()
        self.run_script("scrape.py")
        # course page + empty section 3 + resources.php = 3 requests, >= 1.5 s apart.
        self.assertEqual(len(fake_moodle.Handler.requests), 3, fake_moodle.Handler.requests)
        self.assertGreaterEqual(time.monotonic() - start, 3.0)

    def test_classic_course_and_unicode(self):
        code, out = self.run_script("scrape.py", "--course", "200")
        self.assertEqual(code, 0, out)
        m = self.manifest()
        self.assertEqual(m["course_name"], "Algorithms & Complexity")
        self.assertEqual([(it["type"], it["title"]) for it in m["items"]],
                         [("resource", "Course outline"), ("resource", "الفرز Sorting"), ("folder", "Past exams")])
        self.assertEqual(m["sections"][1]["section_name"], "1 March - 7 March")

    def test_one_section_per_page(self):
        code, out = self.run_script("scrape.py", "--course", "300")
        self.assertEqual(code, 0, out)
        m = self.manifest()
        self.assertEqual([(it["section_number"], it["title"]) for it in m["items"]],
                         [(0, "News"), (1, "OSI model"), (2, "TCP handshake")])

    def test_rerun_keeps_stage3_status_and_never_duplicates(self):
        self.run_script("scrape.py")
        path = self.dir / "data" / "manifest.json"
        m = self.manifest()
        for it in m["items"]:
            if it["id"] == "cm:11":
                it.update(status="downloaded", local_path="downloads/x/01-Week 1/lecture1.pdf")
        path.write_text(json.dumps(m), encoding="utf-8")

        code, out = self.run_script("scrape.py")
        self.assertEqual(code, 0, out)
        m2 = self.manifest()
        self.assertEqual(len(m2["items"]), 10)
        self.assertEqual(len({it["id"] for it in m2["items"]}), 10)
        lec = self.by_id(m2)["cm:11"]
        self.assertEqual((lec["status"], lec["local_path"]), ("downloaded", "downloads/x/01-Week 1/lecture1.pdf"))

    def test_switching_course_parks_and_restores_manifest(self):
        self.run_script("scrape.py")
        path = self.dir / "data" / "manifest.json"
        m = self.manifest()
        m["items"][0].update(status="downloaded", local_path="downloads/x/a.pdf")
        path.write_text(json.dumps(m), encoding="utf-8")

        code, out = self.run_script("scrape.py", "--course", "200")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.manifest()["course_id"], "200")
        self.assertEqual(self.manifest("manifest-course-100.json")["items"][0]["status"], "downloaded")

        code, out = self.run_script("scrape.py", "--course", "100")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.manifest()["items"][0]["status"], "downloaded")
        self.assertFalse((self.dir / "data" / "manifest-course-100.json").exists())
        self.assertTrue((self.dir / "data" / "manifest-course-200.json").exists())

    def test_unknown_theme_does_not_guess(self):
        code, out = self.run_script("scrape.py", "--course", "400")
        self.assertEqual(code, 1, out)
        self.assertIn("No course sections matched", out)
        self.assertTrue((self.dir / "data" / "debug" / "course_page.html").exists())
        self.assertFalse((self.dir / "data" / "manifest.json").exists())

    def test_stray_links_are_reported_not_added(self):
        code, out = self.run_script("scrape.py", "--course", "500")
        self.assertEqual(code, 0, out)
        self.assertEqual([it["id"] for it in self.manifest()["items"]], ["cm:61"])
        self.assertIn("Formula sheet", out)
        self.assertIn("NOT added", out)
        self.assertTrue((self.dir / "data" / "debug" / "course_page.html").exists())

    def test_save_html_flag(self):
        code, out = self.run_script("scrape.py", "--save-html")
        self.assertEqual(code, 0, out)
        html = (self.dir / "data" / "debug" / "course_page.html").read_text(encoding="utf-8")
        self.assertIn("Data Structures (CS201)", html)

    def test_course_that_does_not_exist(self):
        code, out = self.run_script("scrape.py", "--course", "999")
        self.assertEqual(code, 1, out)
        self.assertIn("Can't find data record", out)

    def test_not_enrolled(self):
        code, out = self.run_script("scrape.py", "--course", "600")
        self.assertEqual(code, 1, out)
        self.assertIn("enrolment page", out)

    def test_bad_course_id(self):
        code, out = self.run_script("scrape.py", "--course", "abc")
        self.assertEqual(code, 1, out)
        self.assertIn("must be a number", out)


class TestDownload(Workspace):
    """Stage 3: downloading."""

    COURSE_DIR = Path("downloads") / "Data Structures (CS201)"
    WEEK1 = COURSE_DIR / "01-Week 1 Arrays Lists"

    def path(self, *parts) -> Path:
        return self.dir.joinpath(*parts)

    def download_requests(self) -> list[str]:
        return [r for r in fake_moodle.Handler.requests if "/pluginfile.php/" in r or "/mod/" in r]

    def all_files(self) -> set[str]:
        root = self.path("downloads")
        return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} if root.exists() else set()

    def test_full_download(self):
        fake_moodle.Handler.requests.clear()
        code, out = self.run_script("scrape.py")
        self.assertEqual(code, 0, out)
        c, w = "Data Structures (CS201)", "Data Structures (CS201)/01-Week 1 Arrays Lists"
        self.assertEqual(self.all_files(), {
            f"{c}/00-General/syllabus.pdf",
            f"{w}/Lecture 1 slides.pdf",
            f"{w}/Lab files/lab1.txt",
            f"{w}/Lab files/data/sample data.csv",
            f"{w}/قراءة 1.pdf",
            f"{w}/Homework 1 - instructions.md",
            f"{w}/rubric.pdf",
            f"{w}/hw1.pdf",
            f"{w}/Notes page.html",
            f"{c}/links.md",
        })
        self.assertEqual(self.path(self.WEEK1, "Lecture 1 slides.pdf").read_bytes(),
                         b"fake contents of /pluginfile.php/111/mod_resource/content/1/Lecture 1 slides.pdf")

        md = self.path(self.WEEK1, "Homework 1 - instructions.md").read_text(encoding="utf-8")
        self.assertIn("500-word reflection", md)
        self.assertIn("Due:", md)
        self.assertIn("rubric.pdf", md)
        self.assertNotIn("secret draft", md)  # submissions are never read
        self.assertIn("Big-O cheat sheet", self.path(self.WEEK1, "Notes page.html").read_text(encoding="utf-8"))
        links = self.path(self.COURSE_DIR, "links.md").read_text(encoding="utf-8")
        self.assertIn("[Visualgo](http://example.org/visualgo)", links)
        self.assertIn("## 02 Week 2", links)

        items = self.by_id(self.manifest())
        self.assertEqual(items["cm:10"]["status"], "skipped")
        self.assertIn("forum", items["cm:10"]["note"])
        self.assertEqual(items["cm:15"]["status"], "unavailable")
        downloaded = {i for i, it in items.items() if it["status"] == "downloaded"}
        self.assertEqual(len(downloaded), 8)
        self.assertEqual(items["cm:18"]["target_url"], "http://example.org/visualgo")
        self.assertEqual(items["cm:12"]["local_path"], (self.WEEK1 / "Lab files").as_posix())
        self.assertEqual(len(items["cm:12"]["files"]), 2)
        self.assertEqual(len(items["cm:14"]["files"]), 2)
        self.assertEqual(items["cm:11"]["local_path"], (self.WEEK1 / "Lecture 1 slides.pdf").as_posix())

        reqs = self.download_requests()
        self.assertFalse([r for r in reqs if "/mod/forum/" in r or "/mod/quiz/" in r], reqs)
        self.assertNotIn("example.org", " ".join(reqs))
        self.assertIn("downloaded now      8", out)
        self.assertIn("Files on disk: 9", out)
        self.assertIn("links.md with 1 links", out)
        self.assertFalse(list(self.path("downloads").rglob("*.part")))

    def test_rerun_downloads_nothing(self):
        self.run_script("scrape.py")
        before = self.manifest()["items"]
        fake_moodle.Handler.requests.clear()
        code, out = self.run_script("scrape.py")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.download_requests(), [])
        self.assertEqual(self.manifest()["items"], before)
        self.assertIn("already present     8", out)

    def test_deleted_file_is_fetched_again(self):
        self.run_script("scrape.py")
        self.path(self.WEEK1, "Lecture 1 slides.pdf").unlink()
        fake_moodle.Handler.requests.clear()
        code, out = self.run_script("scrape.py")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.path(self.WEEK1, "Lecture 1 slides.pdf").exists())
        self.assertEqual(self.download_requests(), [
            "/moodle/mod/resource/view.php?id=11&redirect=1",
            "/moodle/pluginfile.php/111/mod_resource/content/1/Lecture%201%20slides.pdf"])

    def test_no_download_flag(self):
        fake_moodle.Handler.requests.clear()
        code, out = self.run_script("scrape.py", "--no-download")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.download_requests(), [])
        self.assertFalse(self.path("downloads").exists())
        self.assertTrue(all(it["status"] in ("pending", "unavailable") for it in self.manifest()["items"]))

    def test_edge_cases_fallback_404_and_name_clash(self):
        code, out = self.run_script("scrape.py", "--course", "700")
        self.assertEqual(code, 0, out)  # one failed item never stops the run
        self.assertEqual(self.all_files(), {"Edge Cases/01-Readings/embedded.pdf",
                                            "Edge Cases/01-Readings/notes.pdf",
                                            "Edge Cases/01-Readings/notes (cm74).pdf"})
        items = self.by_id(self.manifest())
        self.assertEqual(items["cm:72"]["status"], "failed")
        self.assertIn("HTTP 404", items["cm:72"]["note"])
        self.assertIn("Broken file [resource]: HTTP 404", out)
        self.assertEqual(items["cm:73"]["local_path"], "downloads/Edge Cases/01-Readings/notes.pdf")
        self.assertEqual(items["cm:74"]["local_path"], "downloads/Edge Cases/01-Readings/notes (cm74).pdf")

        # Rerun: only the failed item is retried; the clash resolves to the same names.
        fake_moodle.Handler.requests.clear()
        code, out = self.run_script("scrape.py", "--course", "700")
        self.assertEqual(self.download_requests(), [
            "/moodle/mod/resource/view.php?id=72&redirect=1",
            "/moodle/pluginfile.php/172/mod_resource/content/1/missing.pdf"])
        self.assertEqual(len(self.all_files()), 3)

    def test_session_expires_mid_download(self):
        fake_moodle.Handler.expire_files = {"/pluginfile.php/174/mod_resource/content/1/notes.pdf"}
        code, out = self.run_script("scrape.py", "--course", "700")
        self.assertEqual(code, 2, out)
        self.assertIn("Progress so far is saved", out)
        items = self.by_id(self.manifest())
        self.assertEqual(items["cm:71"]["status"], "downloaded")
        self.assertEqual(items["cm:73"]["status"], "downloaded")
        self.assertNotEqual(items["cm:74"]["status"], "downloaded")
        self.assertFalse(list(self.path("downloads").rglob("*.part")))

        fake_moodle.Handler.expire_files = set()
        fake_moodle.Handler.requests.clear()
        code, out = self.run_script("scrape.py", "--course", "700")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.by_id(self.manifest())["cm:74"]["status"], "downloaded")
        reqs = self.download_requests()
        self.assertFalse([r for r in reqs if "id=71" in r or "id=73" in r], reqs)  # not fetched again


if __name__ == "__main__":
    unittest.main(verbosity=2)
