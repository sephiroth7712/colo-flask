import datetime
import functools
import os
import re
import urllib
import time
import hashlib
import random

from flask import (Flask, flash, Markup, redirect, render_template, request,
                   Response, session, url_for)
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache
from peewee import *
from playhouse.flask_utils import FlaskDB, get_object_or_404, object_list
from playhouse.sqlite_ext import *
from flask_uploads import UploadSet, configure_uploads, IMAGES
from werkzeug.utils import secure_filename


# Blog configuration values.



# You may consider using a one-way hash to generate the password, and then
# use the hash again in the login view to perform the comparison. This is just
# for simplicity.
ADMIN_PASSWORD = 'c7233795b805fca07431a103cf32f74d8b41b352eaa0bd7a8bac67b0e0ea9a536a63fe230b30ff8f9262b8392496255fe5ebbfa5d2976d1c3a2b6ca28b234c6f'
APP_DIR = os.path.dirname(os.path.realpath(__file__))

# The playhouse.flask_utils.FlaskDB object accepts database URL configuration.
DATABASE = 'sqliteext:///%s' % os.path.join(APP_DIR, 'blog.db')
DEBUG = False

# The secret key is used internally by Flask to encrypt session data stored
# in cookies. Make this unique for your app.
SECRET_KEY = 'shhh, secret!'

# This is used by micawber, which will attempt to generate rich media
# embedded objects with maxwidth=800.
SITE_WIDTH = 800
UPLOAD_FOLDER = 'static/images/'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

# Create a Flask WSGI app and configure it using values from the module.
app = Flask(__name__)
app.config.from_object(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# FlaskDB is a wrapper for a peewee database that sets up pre/post-request
# hooks for managing database connections.
flask_db = FlaskDB(app)

# The `database` is the actual peewee database, as opposed to flask_db which is
# the wrapper.
database = flask_db.database

# Configure micawber with the default OEmbed providers (YouTube, Flickr, etc).
# We'll use a simple in-memory cache so that multiple requests for the same
# video don't require multiple network requests.
oembed_providers = bootstrap_basic(OEmbedCache())


class Entry(flask_db.Model):
    title = CharField()
    slug = CharField(unique=True)
    content = TextField()
    tags = TextField()
    published = BooleanField(index=True)
    is_highlight = BooleanField(index=True)
    category = TextField()
    date = TextField()
    time = TextField()
    contact = TextField()
    fee = TextField()
    image = TextField()
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)
    @property
    def html_content(self):
        """
        Generate HTML representation of the markdown-formatted blog entry,
        and also convert any media URLs into rich media objects such as video
        players or images.
        """
        hilite = CodeHiliteExtension(linenums=False, css_class='highlight')
        extras = ExtraExtension()
        markdown_content = markdown(self.content, extensions=[hilite, extras])
        oembed_content = parse_html(
            markdown_content,
            oembed_providers,
            urlize_all=True,
            maxwidth=app.config['SITE_WIDTH'])
        return Markup(oembed_content)

    def save(self, *args, **kwargs):
        # Generate a URL-friendly representation of the entry's title.
        if not self.slug:
            self.slug = re.sub('[^\w]+', '-', self.title.lower()).strip('-')
        ret = super(Entry, self).save(*args, **kwargs)

        # Store search content.
        return ret

    @classmethod
    def public(cls):
        return Entry.select().where(Entry.published == True)


def login_required(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if session.get('logged_in'):
            return fn(*args, **kwargs)
        return redirect(url_for('login', next=request.path))
    return inner

@app.route('/login/', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST' and request.form.get('password'):
        password = request.form.get('password')
        hashed = hashlib.sha512(password).hexdigest()
        # TODO: If using a one-way hash, you would also hash the user-submitted
        # password and do the comparison on the hashed versions.
        if hashed == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            session.permanent = True  # Use cookie to store session.
            flash('You are now logged in.', 'success')
            return redirect(next_url or url_for('index'))
        else:
            flash('Incorrect password.', 'danger')
    return render_template('login.html', next_url=next_url)

@app.route('/logout/', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        return redirect(url_for('index'))
    return render_template('logout.html')

@app.route('/')
def index():
    # search_query = request.args.get('q')
    # if search_query:
    #     query = Entry.search(search_query)
    # else:
    #     query = Entry.public().order_by(Entry.timestamp.desc())
    query = Entry.public().order_by(Entry.timestamp.desc())
    # The `object_list` helper will take a base query and then handle
    # paginating the results if there are more than 20. For more info see
    # the docs:
    # http://docs.peewee-orm.com/en/latest/peewee/playhouse.html#object_list
    return object_list(
        'index.html',
        query,
        check_bounds=False)

# This part is for speaker----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
class Speakers(flask_db.Model):
    name = CharField()
    title = TextField()
    about = TextField()
    facebook = TextField()
    twitter = TextField()
    website = TextField()
    image = TextField()
    slug = CharField()
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)

    def save(self, *args, **kwargs):
        # Generate a URL-friendly representation of the entry's title.
        if not self.slug:
            self.slug = re.sub('[^\w]+', '-', self.name.lower()).strip('-')
        ret = super(Speakers, self).save(*args, **kwargs)
        return ret

    @classmethod
    def public(cls):
        return Speakers.select()

def add(speaker, template):
    if request.method == 'POST':
        speaker.name = request.form.get('name') or ''
        speaker.title = request.form.get('title') or ''
        speaker.about = request.form.get('about') or ''
        speaker.facebook = request.form.get('facebook') or ''
        speaker.twitter = request.form.get('twitter') or ''
        speaker.website = request.form.get('website') or ''

        # Uploading Files
        file = request.files['image']
        filename = secure_filename(file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], str(time.time())[4:10] + filename)
        file.save(image_path)
        speaker.image = image_path

        if not (speaker.name and speaker.title):
            flash('Name and Title are required.', 'danger')
        else:
            # Wrap the call to save in a transaction so we can roll it back
            # cleanly in the event of an integrity error.
            try:
                with database.atomic():
                    speaker.save()
            except IntegrityError:
                flash('Error: this name is already in use.', 'danger')
            else:
                flash('speaker saved successfully.', 'success')
                return redirect(url_for('speakers'))

    return render_template(template, speaker=speaker)

@app.route('/add-speaker/', methods=['GET', 'POST'])
def add_speaker():
    return add(Speakers(name='', title=''), 'add-speaker.html')

@app.route('/speakers/')
def speakers():
    query = Speakers.public().order_by(Speakers.name)
    return object_list(
        'speakers.html',
        query,
        check_bounds=False)

@app.route('/<slug>/delete_speaker/')
@login_required
def delete_speaker(slug):
    delete = Speakers.delete().where(Speakers.slug == slug).execute()
    return redirect(url_for('speakers'))

# Speaker Part Done-----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------

# This part is for Survey----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
class EventPref(flask_db.Model):
    name = CharField()
    event_list = TextField()

    def save(self, *args, **kwargs):
        ret = super(EventPref, self).save(*args, **kwargs)
        return ret

    @classmethod
    def public(cls):
        return EventPref.select()

class Survey(flask_db.Model):
    name = CharField()
    department = TextField()
    year = TextField()
    tags = TextField()
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)

    def save(self, *args, **kwargs):
        ret = super(Survey, self).save(*args, **kwargs)
        return ret

    @classmethod
    def public(cls):
        return Survey.select()

@app.route('/survey/', methods=['GET', 'POST'])
def survey():
    return add_survey_entry(Survey(name='', department=''), 'survey.html')

def recommend(tag_list, name):
    # query = Entry.public().where((Entry.tags.contains('Future')) | (Entry.tags.contains('transport')))
    query = Entry.public().where(Entry.tags.contains('highlight'))
    for tag in tag_list:
        query = query | Entry.public().where(Entry.tags.contains(tag))

    return object_list(
        'list.html',
        query,
        check_bounds=False, user=name)

def add_survey_entry(survey, template):
    if request.method == 'POST':
        survey.name = request.form.get('name') or ''
        survey.department = request.form.get('department') or ''
        survey.year = request.form.get('year') or ''
        temp = request.form.getlist('tags_input')
        temp2=[]
        for x in temp:
            temp2.append(x.split('_', 1)[-1])
        survey.tags = ', '.join(temp2) or ''
        if not (survey.name):
            flash('Name required.', 'danger')
        else:
            # Wrap the call to save in a transaction so we can roll it back
            # cleanly in the event of an integrity error.
            try:
                with database.atomic():
                    survey.save()
            except IntegrityError:
                flash('Error: this name is already in use.', 'danger')
            else:
                flash('survey saved successfully.', 'success')
                return recommend(temp2, survey.name)

    return render_template(template)

# Survey Part Done-----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------


@app.route('/events')
def events():
    query = Entry.public().order_by(Entry.timestamp.desc())
    return object_list(
        'list.html',
        query,
        check_bounds=False)


def _create_or_edit(entry, template):
    if request.method == 'POST':
        entry.title = request.form.get('title') or ''
        entry.content = request.form.get('content') or ''
        entry.tags = request.form.get('tags') or ''
        entry.is_highlight = request.form.get('is_highlight') or False
        entry.published = request.form.get('published') or False
        entry.category = request.form.get('category') or ''
        entry.date = request.form.get('date') or ''
        entry.time = request.form.get('time') or ''
        entry.contact = request.form.get('contact') or ''
        entry.fee = request.form.get('fee') or ''
        # Uploading Files
        file = request.files['image']
        filename = secure_filename(file.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], str(time.time())[4:10] + filename)
        file.save(image_path)
        entry.image = image_path

        if not (entry.title and entry.content):
            flash('Title and Content are required.', 'danger')
        else:
            # Wrap the call to save in a transaction so we can roll it back
            # cleanly in the event of an integrity error.
            try:
                with database.atomic():
                    entry.save()
            except IntegrityError:
                flash('Error: this title is already in use.', 'danger')
            else:
                flash('Entry saved successfully.', 'success')
                if entry.published:
                    return redirect(url_for('detail', slug=entry.slug))
                else:
                    return redirect(url_for('edit', slug=entry.slug))

    return render_template(template, entry=entry)

@app.route('/create/', methods=['GET', 'POST'])
@login_required
def create():
    return _create_or_edit(Entry(title='', content=''), 'create.html')

@app.route('/drafts/')
@login_required
def drafts():
    query = Entry.drafts().order_by(Entry.timestamp.desc())
    return object_list('index.html', query, check_bounds=False)

@app.route('/<slug>/')
def detail(slug):
    if session.get('logged_in'):
        query = Entry.select()
    else:
        query = Entry.public()
    entry = get_object_or_404(query, Entry.slug == slug)
    return render_template('detail.html', entry=entry)

@app.route('/<slug>/edit/', methods=['GET', 'POST'])
@login_required
def edit(slug):
    entry = get_object_or_404(Entry, Entry.slug == slug)
    return _create_or_edit(entry, 'edit.html')

@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    # We'll use this template filter in the pagination include. This filter
    # will take the current URL and allow us to preserve the arguments in the
    # querystring while replacing any that we need to overwrite. For instance
    # if your URL is /?q=search+query&page=2 and we want to preserve the search
    # term but make a link to page 3, this filter will allow us to do that.
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)

@app.errorhandler(404)
def not_found(exc):
    return Response('<h3>Not found</h3>'), 404

def main():
    database.create_tables([Entry], safe=True)
    database.create_tables([Speakers], safe=True)
    database.create_tables([Survey], safe=True)
    database.create_tables([EventPref], safe=True)
    app.run(debug=True)

if __name__ == '__main__':
    main()
