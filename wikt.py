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

def get_file(title):
	tree = app.repo.revparse_single("master").tree
	try:
		return app.repo[tree[title].oid]
	except KeyError:
		return None


def commit(builder, message):
	author = git.Signature("Jerome Leclanche", "jerome@leclan.ch")
	parent_commit = app.repo[app.repo.head.target]
	parents = [parent_commit.hex]

	app.repo.create_commit("HEAD", author, WEB_COMMITTER, message, builder.write(), parents)


def commit_file(path, contents, message):
	builder = app.repo.TreeBuilder(app.repo.revparse_single("master").tree)
	builder.insert(path, app.repo.create_blob(contents), git.GIT_FILEMODE_BLOB)
	commit(builder, message)


def delete_file(path, message):
	builder = app.repo.TreeBuilder(app.repo.revparse_single("master").tree)
	builder.remove(path)
	commit(builder, message)


def article_not_found(path, title, error=None):
	# This is a soft 404 error for actual articles that don't exist yet
	return render_template("article/not_found.html", title=title, path=path, error=error), 404


@app.errorhandler(404)
def hard_404(error):
	return render_template("404.html"), 404


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


@app.route("/wiki/<path:path>")
def article_view(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_view", path=_path))
	title = humanize_title(_path)

	file = get_file(title)
	if file is None:
		return article_not_found(path, title)

	return render_template("article/view.html", title=title, contents=file.data.decode(), path=path)


@app.route("/edit/<path:path>", methods=["GET", "POST"])
def article_edit(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_edit", path=_path))
	title = humanize_title(_path)

	file = get_file(title)
	form = EditForm(request.form)

	if request.method == "POST" and form.validate():
		if not form.text.data:
			# The page has been blanked. Ignore the edit if it doesn't exist.
			if file:
				if not form.summary.data:
					form.summary.data = "Blanked the page"
				commit_file(path, form.text.data, form.summary.data)
				flash("The page {} has been blanked".format(title))
		elif form.text.data != (file and file.data.decode()):
			# Commit only if the page is new or if its contents have changed
			commit_file(path, form.text.data, form.summary.data)
			flash("Your changes have been saved")
		else:
			flash("No changes")
		return redirect(url_for("article_view", path=path))

	if file is not None:
		form.text.data = file.data.decode()

	return render_template("article/edit.html", path=path, title=title, form=form, is_new=file is None)

@app.route("/history/<path:path>")
def article_history(path):
	...


@app.route("/delete/<path:path>", methods=["GET", "POST"])
def article_delete(path):
	_path = normalize_title(path)
	if path != _path:
		return redirect(url_for("article_edit", path=_path))
	title = humanize_title(_path)

	file = get_file(title)
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
			builder.insert(file, app.repo.create_blob(contents), git.GIT_FILEMODE_BLOB)
			app.repo.create_commit("HEAD", author, WEB_COMMITTER, "Initial commit", builder.write(), [])

	app.run()
