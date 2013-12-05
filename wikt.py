import os.path
import pygit2 as git
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash


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


def normalize_title(title):
	return title.replace(" ", "_")


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
	return redirect(MAIN_PAGE)


@app.route("/wiki/<path:path>")
def show_page(path):
	title = normalize_title(path)
	if path != title:
		return redirect("/wiki/{}".format(title))

	tree = app.repo.revparse_single("master").tree
	try:
		return app.repo[tree[title].oid].data
	except KeyError:
		return soft_404(path)


if __name__ == "__main__":
	try:
		app.repo = git.Repository(REPOSITORY_PATH)
	except KeyError:
		print("No wiki found. Creating at %r" % (REPOSITORY_PATH))
		app.repo = git.init_repository(REPOSITORY_PATH)
		write_page("Main Page", "Welcome to the wiki!")

	app.run()
