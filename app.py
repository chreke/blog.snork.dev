import re
import markdown
import json
import datetime
import os

from flask import (
    abort,
    Flask,
    Response,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from markupsafe import Markup
from pathlib import Path
from werkzeug.security import safe_join

app = Flask(__name__)

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

def require_authentication():
    auth = request.authorization
    response = Response(
        "You must log in to access this page",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )
    if not auth:
        abort(response)
    if not (auth.username == USERNAME and auth.password == PASSWORD):
        abort(response)

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
def edit():
    require_authentication()
    posts = read_posts()
    return render_template("edit.html", title="Edit posts", posts=posts)

def slugify(string):
    return re.sub(r"[^\w]", "-", string.lower())

@app.route("/new/", methods=["GET", "POST"], defaults={"slug": ""})
@app.route("/edit/<string:slug>", methods=["GET", "POST"])
def edit_post(slug):
    require_authentication()
    settings = load_settings()
    if request.method == "POST":
        title = request.form["title"]
        draft = bool(request.form.get("draft"))
        if not title:
            abort(400, "Title must be set")
        # TODO: This could accidentally clobber other posts, fix this
        if not slug:
            slug = slug or slugify(title)
            now = datetime.datetime.now()
            metadata = {
                "published_at": now.isoformat()
            }
            settings["posts"][slug] = metadata
        content = request.form["content"]
        with open(f"posts/{slug}.md", "w") as f:
            f.write(content)
        settings["posts"][slug]["title"] = title
        settings["posts"][slug]["draft"] = draft
        save_settings(settings)
        return redirect(f"/preview/{slug}.html")
    title = ""
    content = ""
    draft = False
    if slug:
        metadata = settings["posts"].get(slug)
        if not metadata:
            abort(404)
        title = metadata["title"]
        draft = metadata["draft"]
        file_path = safe_join(f"posts/{slug}.md")
        if not file_path:
            abort(404)
        with open(file_path, "r") as f:
            content = f.read()
    return render_template("edit-post.html", title=title, content=content, draft=draft)

@app.route("/preview/<string:slug>.html", methods=["GET"], defaults={"preview": True})
@app.route("/posts/<string:slug>.html", methods=["GET"], defaults={"preview": False})
def view(slug, preview):
    require_authentication()
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
    return render_template(
        "post.html",
        description=post_metadata["description"],
        slug=slug,
        content=content,
        preview=preview,
        title=metadata["title"]
    )

@app.route("/media/<path:path>")
def media(path):
    return send_from_directory('media', path)

# NOTE: Ensure that the "posts" dir exists on startup
ensure_dir_exists(Path("posts"))
