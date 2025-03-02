# blog.snork.dev

This is a *very minimal* [Flask][flask] blog application, mostly intended for
my personal use. However, I thought it might be fun to open source it, so here
it is. Please excuse the somewhat janky code - pull requests are welcome!

## Installation

To run this application you need [Python 3.8][python] or higher.

It is recommended to run this program in a [virtual environment][venv]; you can
create one like this:

```sh
python3 -m venv venv
```

After the virtual environment has been created you need to activate it:

```sh
# Linux
. venv/bin/activate

# Windows
venv\Scripts\Activate.ps1
```

After you've activated your virtual environment install the project
dependencies with:

```sh
pip install -r requirements.txt
```

## Running the application

Before you start the application, you need to create the following environment
variables:

- `AUTH_USER`
- `AUTH_PASSWORD`

These should contain the username and password you should enter to access
protected areas of your blog.

Once the environment variables have been set up, you can start the application
with debugging turned on by running the following command:

```sh
flask --debug run
```

## WSGI

The `flask` command will start the Flask development server, which is fine for
testing but not suitable for "real" usage. Since Flask implements the WSGI
interface you can use it with any WSGI server, e.g. uWSGI or Gunicorn.

For example, to run the application with Gunciron, first install it:

```sh
pip install gunicorn
```

Then start the server like this:

```sh
gunicorn -b 0.0.0.0 app:app
```

## Usage

To create a new post, navigate to the `/edit` page

## Development

This project uses [pip-tools](https://github.com/jazzband/pip-tools) to manage
development dependencies. If you want to work on the app, start by installing
`pip-tools`:

```sh
pip install pip-tools
```

You should now be able to run `make` in the root directory to install and lock
dependencies.

[venv]: https://docs.python.org/3/library/venv.html
[python]: https://www.python.org/
[flask]: https://flask.palletsprojects.com/
