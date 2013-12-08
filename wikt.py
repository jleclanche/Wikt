import os.path
import pygit2 as git
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from forms import EditForm


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

def write_page(title, contents, message):
	author = git.Signature("Jerome Leclanche", "jerome@leclan.ch")

	parent_commit = app.repo[app.repo.head.target]
	parents = [parent_commit.hex]
	tree = app.repo.revparse_single("master").tree
	builder = app.repo.TreeBuilder(tree)

	builder.insert(title, app.repo.create_blob(contents), git.GIT_FILEMODE_BLOB)
	app.repo.create_commit("HEAD", author, WEB_COMMITTER, message, builder.write(), parents)


def soft_404(path):
	return 'There is currently no text in this page. You can <a href="{}">edit it</a>, though.'.format(url_for("article_edit", path=path)), 404

@app.errorhandler(404)
def hard_404(error):
	return 'Are you lost?', 404


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
		return soft_404(path)

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
		# Commit only if the page is new or if its contents have changed
		if form.text.data != (file and file.data.decode()):
			write_page(title, form.text.data, form.summary.data)
			flash("Your changes have been saved")
		else:
			flash("No changes")
		return redirect(url_for("article_view", path=path))

	if file is not None:
		form.text.data = file.data.decode()

	return render_template("article/edit.html", title=title, form=form, is_new=file is None, path=path)

@app.route("/history/<path:path>")
def article_history(path):
	...


@app.route("/delete/<path:path>")
def article_delete(path):
	...


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
