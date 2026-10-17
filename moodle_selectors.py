"""Every CSS selector and URL pattern the scraper relies on, in one place.

If Moodle's layout changes or a theme uses different markup, this should be the
only file to edit. Afterwards run:  python tests/run_tests.py

(Deliberately not called selectors.py: that would shadow Python's built-in
`selectors` module, which Playwright's asyncio machinery imports.)

The selectors below rely on markup from Moodle core (Boost, Classic and most
themes built on them), not on theme styling.
"""

# --- Login detection (common.is_logged_in) -----------------------------------
LOGIN = {
    # Present for any logged-in, non-guest user (inside the user menu).
    "logout_link": 'a[href*="/login/logout.php"]',
    # Shown to guests and logged-out visitors.
    "login_link": 'a[href*="/login/index.php"]',
    "login_form": 'form#login, form.login-form, input[type="password"]',
    # Moodle core adds this <body> class when nobody is logged in.
    "body_class_logged_out": "notloggedin",
}

# --- Course page (scrape.py) -------------------------------------------------
COURSE = {
    # Main content area; the first one that exists is used.
    "main_region": ["#region-main", '[role="main"]'],
    # Moodle error pages (bad course id, no permission).
    "error_box": ".errorbox .errormessage, .errorbox, #notice",
    "course_title": ".page-header-headings h1, #page-header h1, .page-context-header h1, header h1, h1",
    # One element per section/week. Nested matches (4.5 subsections) are folded into their parent.
    "section": 'li.section, [data-for="section"], .course-section, section[id^="section-"]',
    # Priority lists: tried in order, first match wins. (A comma list would return whichever comes
    # first in the page; in Moodle 4.x that's the whole header bar, including "Collapse all".)
    "section_name": [".sectionname", 'h3[data-for="section_title"]', "h3", "h2", "h4"],
    # One element per activity (file, folder, forum, label, ...).
    "activity": 'li.activity, [data-for="cmitem"]',
    "activity_name": [".instancename", ".activityname", '[data-for="activityname"]'],  # priority list
    "activity_name_attr_holder": "[data-activityname]",  # 4.x stores the name in data-activityname
    "restriction_info": '.availabilityinfo, [data-region="availabilityinfo"]',
    # Text hidden from sighted users (e.g. " File" after a resource name).
    "hidden_text": ".accesshide, .sr-only, .visually-hidden, .badge",
    # Direct file links inside labels, section summaries and activity descriptions.
    "inline_file_link": 'a[href*="/pluginfile.php/"]',
    # Activity links found inside these are navigation, not course content.
    "not_content": 'nav, .breadcrumb, #page-navbar, .activity-navigation, [data-region="drawer"], .block',
}

# --- Moodle's own resource list: /course/resources.php?id=<course> ----------------
RESOURCE_INDEX = {
    "rows": '#region-main table tr, [role="main"] table tr',
    "header_cell": 'th[scope="col"]',
}

# --- URL and attribute patterns (JavaScript regex syntax) ------------------------
PATTERNS = {
    # /mod/<module>/view.php?id=<course module id>
    "activity_url": r"/mod/([a-z0-9_]+)/view\.php\?(?:[^#]*&)?id=(\d+)",
    # <li id="module-123">
    "activity_id_attr": r"module-(\d+)",
    # <li class="activity modtype_resource">
    "module_class": r"\bmodtype_([a-z0-9_]+)",
    # <li id="section-3">
    "section_id_attr": r"^section-(\d+)$",
    # Links to a single-section page. {course_id} is filled in at runtime.
    "section_page_url": (r"/course/(?:view\.php\?(?:[^#]*&)?id={course_id}&(?:[^#]*&)?section=(\d+)"
                         r"|section\.php\?(?:[^#]*&)?id=(\d+))"),
}

# --- Classification -------------------------------------------------------------
# Module name from the URL -> manifest "type". Anything else becomes "other".
KNOWN_TYPES = {"resource", "folder", "page", "url", "assign"}
# Not recorded in the manifest (labels' file links are recorded as inline_file).
IGNORED_MODULES = {"label", "subsection"}
