"""
    == Making The Plugins Available ==
    
    If pysmvt is installed, you should see the following in the output of
    `nosetests --help`:
    
        ...
        --pysmvt-app-profile=PYSMVT_PROFILE
                    The name of the test profile in settings.py
        ...
    
    == Using the Plugins ==
    
    You **must** be inside a pysmvt application's package directory for
    these plugins to work:
    
        `cd .../myproject/src/myapp-dist/myapp/`
    
    === Init Current App Plugin ===
    
    This plugin does two things:
        
        - initializes a WSGI application for the current application
          (optionally allowing you to specify which profile you want used
          to initlize the application)
        - automatically includes test's from packages if so defined in the
          profile which is loaded.
    
    You don't have to do anything explicit to use this plugin.  It is
    enabled automatically when `nosetests` is run from inside an
    application's directory structure.  Assuming your make_wsgi() function
    is setup correctly, globaly proxy objects like 'ag' should now function
    correctly.  Request level objects, like 'rg' will not yet be available
    however.
    
    In order to get access to the wsgi application that was instantiated,
    you can do:
        
        from pysmvt import ag
        
        testapp = ag._wsgi_test_app
        
    `testapp` could now be used in the pysmvt.utils.wrapinapp() decorator.
    
    The default profile used with this plugin is 'Test'.  If you need to
    specifiy a different profile, do:
        
        `nosetests  --pymvt-app-profile=mytestprofile`
        
    To include tests from packges outside the application's directory
    structure, you can put a `testing.include_pkgs` attribute in your test
    profile. For example:
    
        class TestPysapp(Test):
            def __init__(self):
                # call parent init to setup default settings
                Test.__init__(self)
                
                # include pysapp tests
                self.testing.include_pkgs = 'pysapp'
        testpysapp = TestPysapp
    
    Running:
        
        `nosetests  --pysmvt-app-profile=testpysapp`
    
    Would be equivelent to running:
    
        `nosetests pysapp`
    
    Packages can also be specified as a list/tuple:
        
        # include multiple tests
        self.testing.include_pkgs = ('pysapp', 'somepkg')        
"""

import os
import logging
import nose.plugins
from nose.tools import make_decorator
from pysmvt import ag, settings
from pysmvt.script import _app_name
from pysmvt.utils import import_app_str
from pysmvt.wrappers import Request
from pysutils import tolist, import_split
from werkzeug import Client as WClient, BaseRequest, EnvironBuilder

class InitCurrentAppPlugin(nose.plugins.Plugin):
    opt_app_profile = 'pysmvt_profile'
    val_app_profile = None
    opt_app_name = 'pysmvt_name'
    val_app_name = None
    opt_disable = 'pysmvt_disable'
    val_disable = False
    
    def add_options(self, parser, env=os.environ):
        """Add command-line options for this plugin"""
        env_opt = 'NOSE_WITH_%s' % self.name.upper()
        env_opt.replace('-', '_')

        parser.add_option("--pysmvt-app-profile",
                          dest=self.opt_app_profile, type="string",
                          default="Test",
                          help="The name of the test profile in settings.py"
                        )
        
        parser.add_option("--pysmvt-app-name",
                          dest=self.opt_app_profile, type="string",
                          default="Test",
                          help="The name of the application's package, defaults"
                          " to top package of current working directory"
                        )
        
        parser.add_option("--pysmvt-disable",
                          dest=self.opt_disable,
                          action="store_true",
                          help="Disable plugin"
                        )
        
    def configure(self, options, conf):
        """Configure the plugin"""
        self.val_disable = getattr(options, self.opt_disable, False)
        if not self.val_disable:
            if hasattr(options, self.opt_app_profile):
                self.val_app_profile = getattr(options, self.opt_app_profile)
            if hasattr(options, self.opt_app_name):
                self.val_app_name = getattr(options, self.opt_app_name)
            else:
                try:
                    self.val_app_name = _app_name()
                except Exception, e:
                    if 'package name could not be determined' not in str(e):
                        raise
                if not self.val_app_name:
                    self.val_disable = True
        
        if not self.val_disable:
            apps_pymod = __import__('%s.applications' % self.val_app_name, globals(), locals(), [''])
            ag._wsgi_test_app = apps_pymod.make_wsgi(self.val_app_profile)
            
            # an application can define functions to be called after the app
            # is initialized but before any test inspection is done or tests
            # are ran.  We call those functions here:
            for callstring in tolist(settings.testing.init_callables):
                tocall = import_app_str(callstring)
                tocall()

    def loadTestsFromNames(self, names, module=None):
        if not self.val_disable:
            try:
                names.extend(tolist(settings.testing.include_pkgs))
            except AttributeError, e:
                if "has no attribute 'testing'" not in str(e):
                    raise

class Client(WClient):
    
    def open(self, *args, **kwargs):
        """
            if follow_redirects is requested, a (BaseRequest, response) tuple
            will be returned, the request being the last redirect request
            made to get the response
        """
        fr = kwargs.get('follow_redirects', False)
        if fr:
            kwargs['as_tuple'] = True
        retval = WClient.open(self, *args, **kwargs)
        if fr:
            return BaseRequest(retval[0]), retval[1]
        return retval

def mock_smtp(cancel_override=True):
    ''' A decorator that allows you to test emails that are sent during
        functional or unit testing by mocking SMTP lib objects with the
        MiniMock library and giving the test function the tracker object
        to do tests with.
        
        :param cancel_override: in testing, we often will have email_overrides
            set so that emails don't get sent out for real.  Since this function
            prevents live emails from being sent, we will most often want
            to cancel that setting for the duration of the test so that the
            email tested is exactly what would be sent out if the emails were
            live.
        :raises: :exc:`ImportError` if the MiniMock library is not installed
        
    Example use::

    @mock_smtp()
    def test_user_form(self, mm_tracker=None):
        add_new_user_which_sends_email_to_user(form_data)
        look_for = """Called smtp_connection.sendmail(
    '...',
    [u'%s'],
    'Content-Type:...To: %s...You have been added to our """ \
            """system of registered users...REQUIRED to change it...
Called smtp_connection.quit()""" % (form_data['email_address'], form_data['email_address'])
        assert mm_tracker.check(look_for), mm_tracker.diff(look_for)
        # make sure only one email is sent out.  Can't == b/c from address
        # will change, but length is ~837, so 1000 seems safe
        assert len(mm_tracker.dump()) <= 1000, len(mm_tracker.dump())
          
        @mock_smtp()
        def test_that_fails():
            assert mm_tracker.check('Called smtp_connection.sendmail(...%s...has been issu'
                        'ed to reset the password...' % user.email_address)
    
    Other tracker methods::
        mm_tracker.dump(): returns minimock usage captured so far
        mm_tracker.diff(): returns diff of expected output and actual output
        mm_tracker.clear(): clears the tracker of everything captured
    '''
    try:
        import minimock
    except ImportError:
        raise ImportError('use of the assert_email decorator requires the minimock library')
    import smtplib
    def decorate(func):
        def newfunc(*arg, **kw):
            try:
                override = None
                # setup the mock objects so we can test the email getting sent out
                tt = minimock.TraceTracker()
                smtplib.SMTP = minimock.Mock('smtplib.SMTP', tracker=None)
                smtplib.SMTP.mock_returns = minimock.Mock('smtp_connection', tracker=tt)
                if cancel_override:
                    override = settings.emails.override
                    settings.emails.override = None
                kw['mm_tracker'] = tt
                func(*arg, **kw)
            finally:
                minimock.restore()
                if cancel_override:
                    settings.emails.override = override
        newfunc = make_decorator(func)(newfunc)
        return newfunc
    return decorate

class LoggingHandler(logging.Handler):
    """ logging handler to check for expected logs when testing"""

    def __init__(self, *args, **kwargs):
        self.reset()
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        self.messages[record.levelname.lower()].append(record.getMessage())

    def reset(self):
        self.messages = {
            'debug': [],
            'info': [],
            'warning': [],
            'error': [],
            'critical': [],
        }

def logging_handler(logger_to_examine):
    lr = logging.getLogger(logger_to_examine)
    lh = LoggingHandler()
    lr.addHandler(lh)
    return lh

def create_request(data, method='POST', bind_to_context=True, **kwargs):
    """
    used to create a fake request that then binds itself to rg.request.  Useful
    for testing forms without needing to use a WSGI client.
    """
    builder = EnvironBuilder(method=method, data=data, **kwargs)
    env = builder.get_environ()
    return Request(env, bind_to_context=bind_to_context)
