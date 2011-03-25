import os
from string import ascii_letters, digits
from random import choice
from datetime import datetime

from google.appengine.ext.webapp import template
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache
import simplejson as json

_CHARS = ascii_letters + digits
_MAX_TENTATIVE = 1000
_ROOT_URL = 'http://b-i-m-al.appspot.com'

class UrlStore(db.Model):
    """model for the store which will have short url, long url and the creation time"""
    short_url_key = db.StringProperty(required=True)
    long_url = db.LinkProperty(required=True)
    creation_date = db.DateTimeProperty()

def _random_id(length=10):
    return ''.join([choice(_CHARS) for i in range(length)])

def _generate_short_url( long_url_value ):
    """ Generate the short url from the original url.
    First check if the url present in the memcache if not check in the model store and again that fails, create one."""
    short_url_id = memcache.get(long_url_value)
    if short_url_id is not None:
        return '%s/%s' % (_ROOT_URL, short_url_id)
    url_matches = db.GqlQuery("SELECT * FROM UrlStore WHERE long_url  = :1", long_url_value)
    if url_matches.count()>0:
        for url in url_matches:
            memcache.add(long_url_value, url.short_url_key, 7200)
            memcache.add(url.short_url_key, long_url_value, 7200)
            return '%s/%s' % (_ROOT_URL, url.short_url_key)
    tentatives = 0
    while tentatives < _MAX_TENTATIVE:
        short_url_id = _random_id()
        
        if db.GqlQuery("SELECT * FROM UrlStore WHERE short_url_key  = :1", short_url_id).count() == 0:
            
            url_obj = UrlStore(short_url_key=short_url_id, long_url=db.Link(long_url_value), creation_date=datetime.now())
            url_obj.put()
            memcache.add(long_url_value, short_url_id, 7200)
            memcache.add(short_url_id, long_url_value, 7200)
            return '%s/%s' % (_ROOT_URL, short_url_id)
        tentatives += 1

class Url(webapp.RequestHandler):
    """GET request processor when the short url is accessed, check if in memcached if not in model store and redirect
    to original url otherwise a 404 error """
    def get(self, url):
        url = url.strip()
        long_url_id = memcache.get(url)
        if long_url_id is not None:
            self.redirect("%s"%long_url_id)
        url_matches = db.GqlQuery("SELECT * FROM UrlStore WHERE short_url_key  = :1", url)
        if url_matches.count()>0:
            for url_match in url_matches:
                self.redirect("%s"%url_match.long_url)
        else:
            self.response.clear()
            self.response.set_status(404)
            self.response.out.write("Not found")

class Home(webapp.RequestHandler):        
    """ Home page of the website"""
    def get(self):
        template_values = {}
        path = os.path.join(os.path.dirname(__file__), 'template/index.html')
        self.response.out.write(template.render(path, template_values))

class Shortner(webapp.RequestHandler):
    def post( self ):
        """Creates, store a short url and return json result back"""
        
        url = self.request.get('longurl').strip()
        short_url = _generate_short_url( url )
        return_context = {'short_url':short_url}
        self.response.headers['Content-Type'] = 'text/json'
        self.response.out.write(json.dumps(return_context))


"""Url definitions"""
application = webapp.WSGIApplication(
    [('/', Home),
     ('/shorten/', Shortner),
     ('/(.*)', Url)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()