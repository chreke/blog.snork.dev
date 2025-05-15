import re
import markdown
import json
import datetime
import os
import secrets
from functools import wraps

from flask import (
    abort,
    Flask,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markupsafe import Markup
from pathlib import Path
from werkzeug.security import safe_join

app = Flask(__name__)
app.config["SERVER_NAME"] = "blog.snork.dev"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True

SETTINGS_FILE = "posts/settings.json"
USERNAME = os.environ["AUTH_USER"]
PASSWORD = os.environ["AUTH_PASSWORD"]

def load_settings():
    if not Path(SETTINGS_FILE).exists():
        return {"posts": {}}
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (request.form["username"] == USERNAME and
            request.form["password"] == PASSWORD):
            session["authenticated"] = True
            next_page = request.args.get("next", url_for("index"))
            return redirect(next_page)
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error, title="Login")

@app.route("/logout")
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("index"))

def read_posts():
    posts = [{"slug": k, **v} for k, v in load_settings()["posts"].items()]
    return sorted(
        posts,
        key=lambda x: x["published_at"],
        reverse=True
    )

class ExtractMetaProcessor(Treeprocessor):
    @staticmethod
    def clean_string(string):
        return Markup(string).striptags()

    def run(self, root):
        metadata = {}
        first_heading = None
        first_paragraph = None

        for element in root:
            if element.tag == "h1" and not first_heading:
                first_heading = "".join(element.itertext())
            elif element.tag == "p" and not first_paragraph:
                first_paragraph = "".join(element.itertext())

            if first_heading and first_paragraph:
                break

        metadata["title"] = first_heading
        metadata["description"] = first_paragraph
        setattr(self.md, "metadata", metadata)
        return None

class ExtractMeta(Extension):
    def extendMarkdown(self, md):
        # NOTE: Priority needs to be lower than the inline tag processor to
        # make sure inline elements are converted to HTML tags before we try to
        # extract metadata
        md.treeprocessors.register(ExtractMetaProcessor(md), "extract_meta", 10)

def ensure_dir_exists(path):
    path.mkdir(parents=True, exist_ok=True)

@app.route("/", methods=["GET"])
def index():
    posts = filter(lambda x: not x["draft"], read_posts())
    return render_template(
        "index.html",
        posts=posts,
        title="blog.snork.dev"
    )

@app.route("/edit/", methods=["GET"])
@auth_required
def edit():
    posts = read_posts()
    return render_template("edit.html", title="Edit posts", posts=posts)

def slugify(string):
    return re.sub(r"[^\w]", "-", string.lower())

@app.route("/new/", methods=["GET", "POST"], defaults={"slug": ""})
@app.route("/edit/<string:slug>.html", methods=["GET", "POST"])
@auth_required
def edit_post(slug):
    settings = load_settings()
    if request.method == "POST":
        title = request.form["title"].strip()
        # TODO: Add date validation
        published_at = request.form["published_at"]
        draft = bool(request.form.get("draft"))
        if not title:
            abort(400, "Title must be set")
        if not slug:
            slug = slug or slugify(title)
            if slug in settings["posts"]:
                abort(400, "Post with this slug already exists")
            settings["posts"][slug] = {}
        content = request.form["content"]
        with open(f"posts/{slug}.md", "w") as f:
            f.write(content)
        post = settings["posts"][slug]
        post["title"] = title
        post["draft"] = draft
        post["published_at"] = published_at
        save_settings(settings)
        return redirect(f"/posts/{slug}.html")
    metadata = {
        "title": "",
        "draft": False,
        "published_at": datetime.datetime.now().date().isoformat()
    }
    content = ""
    if slug:
        metadata = settings["posts"].get(slug)
        if not metadata:
            abort(404)
        file_path = safe_join(f"posts/{slug}.md")
        if not file_path:
            abort(404)
        with open(file_path, "r") as f:
            content = f.read()
    return render_template("edit-post.html", content=content, **metadata)

@app.route("/posts/<string:slug>.html", methods=["GET"])
def view(slug):
    settings = load_settings()
    metadata = settings["posts"].get(slug)
    if not metadata:
        abort(404)
    post_file = slug + ".md"
    path = safe_join("posts", post_file)
    if not path:
        abort(404)
    with open(path, "r") as f:
        md = markdown.Markdown(
            extensions=[
                "fenced_code",
                "codehilite",
                "smarty",
                "toc",
                "footnotes",
                ExtractMeta(),
            ])
        content = md.convert(f.read())
        post_metadata = getattr(md, "metadata", {})

    # Show edit link for authenticated users
    show_edit = session.get("authenticated", False)

    return render_template(
        "post.html",
        description=post_metadata["description"],
        slug=slug,
        content=content,
        show_edit=show_edit,
        title=metadata["title"]
    )

@app.route("/media/<path:path>")
def media(path):
    return send_from_directory('media', path)

@app.route("/feed.xml", methods=["GET"])
def feed():
    posts = [p for p in read_posts() if not p["draft"]]
    feed_content = render_template("feed.xml", posts=posts)
    return Response(feed_content, mimetype="application/rss+xml")

# NOTE: Ensure that the "posts" dir exists on startup
ensure_dir_exists(Path("posts"))
