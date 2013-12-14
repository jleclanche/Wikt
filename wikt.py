import os.path
import pygit2 as git
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from forms import DeleteForm, EditForm


# configuration
DATABASE = "/tmp/wikt.db"
DEBUG = True
SECRET_KEY = "~AyQ1#7{.d ?}oQi3iA@=I%KrBmp}z_*|w9-+1N[>En?HLbswCQ_O>g{eWz/Y[HraS/i<?0:vjW"
USERNAME = "admin"
PASSWORD = "default"
WIKI_NAME = "test-wiki"
REPOSITORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wikis", WIKI_NAME)
WEB_COMMITTER = git.Signature("Wikt Web Interface", "root@wikt")
MAIN_PAGE = "Main_Page"

app = Flask(__name__)
app.config.from_object(__name__)


namespaces = {"special"}

def firstcap(s):
	return s[0].upper() + s[1:]

def normalize_title(title):
	"""
	Mediawiki-compatible title normalization
	"""
	title = title.replace(" ", "_")
	if ":" in title:
		namespace, title = title.split(":")
		if namespace.lower() not in namespaces:
			return hard_404("No such namespace")
		title = "{}:{}".format(namespace.capitalize(), firstcap(title))
	else:
		title = firstcap(title)

	return title

def humanize_title(title):
	title = title.replace("_", " ")
	return title

def get_file(title, commit="master"):
	tree = app.repo.revparse_single(commit).tree
	try:
		return app.repo[tree[title].oid]
	except KeyError:
		return None


def commit(builder, message):
	author = git.Signature("Jerome Leclanche", "jerome@leclan.ch")
	parent_commit = app.repo[app.repo.head.target]
	parents = [parent_commit.hex]

	app.repo.create_commit("HEAD", author, WEB_COMMITTER, message, builder.write(), parents)


def iter_commits(path, head):
	# There is no way in libgit/libgit2/pygit2 to get the commits affecting a specific file.
	# Git does it by walking the entire commit tree. So do we.
	last_commit = None
	last_oid = None
	for commit in app.repo.walk(head, git.GIT_SORT_TIME):
		if path in commit.tree:
			oid = commit.tree[path].oid
			if oid != last_oid and last_oid:
				yield last_commit

			last_oid = oid
		else:
			last_oid = None

		last_commit = commit

	if last_oid:
		yield last_commit

def commit_file(path, contents, message):
	builder = app.repo.TreeBuilder(app.repo.revparse_single("master").tree)
	builder.insert(path, app.repo.create_blob(contents), git.GIT_FILEMODE_BLOB)
	commit(builder, message)


def delete_file(path, message):
	builder = app.repo.TreeBuilder(app.repo.revparse_single("master").tree)
	builder.remove(path)
	commit(builder, message)


def get_request_commit():
	return app.repo.revparse_single(request.args.get("commit", "master")).oid


def article_not_found(path, title, error=None):
	# This is a soft 404 error for actual articles that don't exist yet
	return render_template("article/not_found.html", title=title, path=path, error=error), 404


@app.errorhandler(404)
def hard_404(error):
	return render_template("404.html"), 404


@app.route("/")
@app.route("/wiki/")
def index():
	return redirect(url_for("article_view", path=MAIN_PAGE))


@app.route("/wiki/Special:AllPages")
def all_pages():
	tree = app.repo.revparse_single("master").tree
	pages = [f.name for f in tree]
	return render_template("special/all_pages.html", pages=pages)


@app.route("/wiki/Special:RecentChanges")
def recent_changes():
	commits = []
	for oid in app.repo:
		obj = app.repo[oid]
		if obj.type == git.GIT_OBJ_COMMIT:
			commits.append({
				"hash": obj.hex,
				"message": obj.message,
				"date": obj.commit_time,
				"author": obj.author.name,
			})
	return render_template("special/recent_changes.html", commits=commits)


@app.route("/diff/<path:path>")
def article_diff(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_view", path=_path))
	title = humanize_title(_path)

	curid = request.args.get("commit", "master")
	oldid = request.args.get("oldid")

	file = get_file(path, curid)
	if file is None:
		return article_not_found(path, title)

	diff = app.repo.diff(oldid, curid)

	return render_template("article/diff.html", title=title, diff=diff)


@app.route("/wiki/<path:path>")
def article_view(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_view", path=_path))
	title = humanize_title(_path)

	file = get_file(path, get_request_commit().hex)
	if file is None:
		return article_not_found(path, title)

	return render_template("article/view.html", title=title, contents=file.data.decode(), path=path)


def clean_data(data):
	"""
	Clean a file before committing it.
	"""
	if not data.endswith("\n"):
		data += "\n"
	return data


class CommitMessage(object):
	def __init__(self, s):
		self.s = s
		self.notes = set()

	def __bool__(self):
		return bool(self.s)

	def get_message(self):
		self.s = self.s.strip()
		while "\n\n" in self.s:
			self.s = self.s.replace("\n\n", "\n")
		return self.s + "\n\n" + "\n".join(self.notes)

	def default_note(self, note):
		if not self.s:
			self.s = note
		else:
			self.notes.add("Note: {}".format(note))


def summarize(s):
	if len(s) > 50:
		return s[:47] + "..."
	return s


@app.route("/edit/<path:path>", methods=["GET", "POST"])
def article_edit(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_edit", path=_path))
	title = humanize_title(_path)

	file = get_file(path, get_request_commit().hex)
	form = EditForm(request.form)

	if request.method == "POST" and form.validate():
		summary = CommitMessage(form.summary.data)
		contents = form.text.data.strip()

		if file:
			if contents == file.data.decode().strip():
				# No changes.
				flash("No changes.")
				return redirect(url_for("article_view", path=path))

			if not contents and not summary:
				# The page has been blanked.
				summary.default_note("Blanked the page")
		else:
			# the page is new
			if not contents:
				# The page doesn't exist and has been sent blank. Ignore the commit.
				flash("The page was not created.")
				return redirect(url_for("article_view", path=path))
			else:
				summary.default_note('Created page with "{}"'.format(summarize(contents)))

		if form.minor_edit.data:
			summary.notes.add("Minor-Edit")

		summary.default_note("→ [[{}]]".format(title))
		commit_file(path, clean_data(contents), summary.get_message())
		flash("Your changes have been saved")
		return redirect(url_for("article_view", path=path))

	if file is not None:
		form.text.data = file.data.decode().strip()

	return render_template("article/edit.html", path=path, title=title, form=form, is_new=file is None)


@app.route("/history/<path:path>")
def article_history(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_edit", path=_path))
	title = humanize_title(_path)
	commits = []

	head = get_request_commit()

	for commit in iter_commits(path, head):
		commits.append({
			"hex": commit.hex,
			"message": commit.message,
			"date": commit.commit_time,
			"author": commit.author.name,
		})

	return render_template("article/history.html", path=path, title=title, commits=commits)


@app.route("/delete/<path:path>", methods=["GET", "POST"])
def article_delete(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_edit", path=_path))
	title = humanize_title(_path)

	file = get_file(title, "master")
	if not file:
		return article_not_found(path, title, error="This page cannot be deleted because it does not exist.")
	form = DeleteForm(request.form)

	if request.method == "POST" and form.validate():
		delete_file(path, form.summary.data)
		flash("The page {} has been deleted".format(title))
		return render_template("article/delete_complete.html")

	return render_template("article/delete.html", path=path, title=title, form=form)


REPO_TEMPLATE = {
	MAIN_PAGE: "Welcome to the wiki. This is the main page.",
	"Help:Contents": "Do you need help?",
}

if __name__ == "__main__":
	try:
		app.repo = git.Repository(REPOSITORY_PATH)
	except KeyError:
		print("No wiki found. Creating at %r" % (REPOSITORY_PATH))
		app.repo = git.init_repository(REPOSITORY_PATH)
		author = git.Signature("Jerome Leclanche", "jerome@leclan.ch")
		builder = app.repo.TreeBuilder()
		for file, contents in REPO_TEMPLATE.items():
			builder.insert(file, app.repo.create_blob(clean_data(contents)), git.GIT_FILEMODE_BLOB)
			app.repo.create_commit("HEAD", author, WEB_COMMITTER, "Initial commit", builder.write(), [])

	app.run()
