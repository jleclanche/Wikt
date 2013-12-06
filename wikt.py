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
MAIN_PAGE = "Main Page"

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

def get_file(title):
	tree = app.repo.revparse_single("master").tree
	try:
		return app.repo[tree[title].oid]
	except KeyError:
		return None

def write_page(title, contents):
	title = normalize_title(title)
	blob = app.repo.create_blob(contents)
	tree = app.repo.TreeBuilder()
	tree.insert(title, blob, git.GIT_FILEMODE_BLOB)
	oid = tree.write()
	author = git.Signature("Jerome Leclanche", "jerome@leclan.ch")
	app.repo.create_commit("HEAD", author, committer, "Initial commit", oid, [])


def soft_404(error):
	return 'There is currently no text in this page. You can <a href="/edit/{}">edit it</a>, though.'.format(error), 404

@app.errorhandler(404)
def hard_404(error):
	return 'Are you lost?', 404


@app.route("/wiki/")
def index():
	return redirect("/wiki/" + MAIN_PAGE)

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
	return render_template("recent_changes.html", commits=commits)


@app.route("/wiki/<path:path>")
def show_page(path):
	title = normalize_title(path)
	if path != title:
		return redirect("/wiki/{}".format(title))

	file = get_file(title)
	if file is None:
		return soft_404(path)
	return file.data


@app.route("/edit/<path:path>", methods=["GET", "POST"])
def edit_page(path):
	title = normalize_title(path)
	if path != title:
		return redirect("/edit/{}".format(title))

	form = EditForm(request.form)

	file = get_file(title)
	if file is not None:
		form.text.data = file.data.decode()

	return render_template("edit_page.html", form=form)


if __name__ == "__main__":
	try:
		app.repo = git.Repository(REPOSITORY_PATH)
	except KeyError:
		print("No wiki found. Creating at %r" % (REPOSITORY_PATH))
		app.repo = git.init_repository(REPOSITORY_PATH)
		write_page("Main Page", "Welcome to the wiki!")

	app.run()
