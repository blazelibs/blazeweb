import unittest
import os
import os.path as path
import rcsutils
import config

# setup the virtual environment so that we can import specific versions
# of system libraries but also ensure that our pysmvt module is what
# we are pulling from
rcsutils.setup_virtual_env('pysmvt-libs-trunk', __file__, '..')

from pysmvttestapp.application import Webapp
from pysmvt.mail import EmailMessage, BadHeaderError, EmailMultiAlternatives, \
    MarkdownMessage, HtmlMessage, send_mail
from pysmvt.application import request_context_manager as rcm

_send_live = True
_to = 'randy@rcs-comp.com'

class TestEmail(unittest.TestCase):
    def setUp(self):
        self.app = Webapp()
    
    def test_normal_ascii(self):
        """Test normal ascii character case"""
        email = EmailMessage('Subject', 'Content', 'from@example.com', ['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'from@example.com'
        assert message['To'] == 'to@example.com'
    
    def test_multi_recip(self):
        email = EmailMessage('Subject', 'Content', 'from@example.com', ['to@example.com','other@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'from@example.com'
        assert message['To'] == 'to@example.com, other@example.com'
    
    def test_header_inj_sub(self):
        email = EmailMessage('Subject\nInjection Test', 'Content', 'from@example.com', ['to@example.com'])
        
        try:
            message = email.message()
        except BadHeaderError, e:
            assert 'Header values can\'t contain newlines' in str(e)
        else:
            self.fail("header injection allowed in subject")
    
    def test_header_inj_from(self):
        email = EmailMessage('From Injection Test', 'Content', 'from@example.com\nto:spam@example.com', ['to@example.com'])
        
        try:
            message = email.message()
        except BadHeaderError, e:
            assert 'Header values can\'t contain newlines' in str(e)
        else:
            self.fail("header injection allowed in from")

    def test_long_subj(self):
        # Test for space continuation character in long (ascii) subject headers (#7747)
        expected = 'Content-Type: text/plain; charset="utf-8"\nMIME-Version: 1.0\nContent-Transfer-Encoding: quoted-printable\nSubject: Long subject lines that get wrapped should use a space continuation\n character to get expected behaviour in Outlook and Thunderbird\nFrom: from@example.com\nTo: to@example.com'
        email = EmailMessage('Long subject lines that get wrapped should use a space continuation character to get expected behaviour in Outlook and Thunderbird', 'Content', 'from@example.com', ['to@example.com'])
        message = email.message()
        assert message.as_string().startswith(expected)

    def test_default_from(self):
        email = EmailMessage('Subject', 'Content', to=['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'

    def test_extra_header(self):
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], headers = {'Reply-To': 'replyto@example.com'})
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Reply-To'] == 'replyto@example.com'
    
    def test_reply_to(self):
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], reply_to='replyto@example.com')
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Reply-To'] == 'replyto@example.com'
    
    def test_reply_to_default(self):
        self.app.settings.emails.reply_to = 'replyto@example.com'
        email = EmailMessage('Subject', 'Content', to=['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Reply-To'] == 'replyto@example.com'
        
    def test_bcc(self):
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], bcc=['bcc1@example.com', 'bcc2@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert email.recipients() == ['to@example.com', 'bcc1@example.com', 'bcc2@example.com']
    
    def test_bcc_defaults(self):
        self.app.settings.emails.bcc_defaults = ['bcc1@example.com', 'bcc2@example.com']
        email = EmailMessage('Subject', 'Content', to=['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert email.recipients() == ['to@example.com', 'bcc1@example.com', 'bcc2@example.com']
        
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], bcc=['bcc3@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert email.recipients() == ['to@example.com', 'bcc3@example.com']

    def test_cc(self):
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], cc=['cc1@example.com', 'cc2@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Cc'] == 'cc1@example.com, cc2@example.com'
        assert email.recipients() == ['to@example.com', 'cc1@example.com', 'cc2@example.com']
    
    def test_cc_defaults(self):
        self.app.settings.emails.cc_defaults = ['cc1@example.com', 'cc2@example.com']
        email = EmailMessage('Subject', 'Content', to=['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Cc'] == 'cc1@example.com, cc2@example.com'
        assert email.recipients() == ['to@example.com', 'cc1@example.com', 'cc2@example.com']
        
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], cc=['cc3@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Cc'] == 'cc3@example.com'
        assert email.recipients() == ['to@example.com', 'cc3@example.com']
        
    def test_bcc_always(self):
        self.app.settings.emails.bcc_always = ['bcc1@example.com', 'bcc2@example.com']
        email = EmailMessage('Subject', 'Content', to=['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert email.recipients() == ['to@example.com', 'bcc1@example.com', 'bcc2@example.com']
        
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], bcc=['bcc3@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert email.recipients() == ['to@example.com',  'bcc3@example.com', 'bcc1@example.com', 'bcc2@example.com']
    
        
    def test_cc_always(self):
        self.app.settings.emails.cc_always = ['cc1@example.com', 'cc2@example.com']
        email = EmailMessage('Subject', 'Content', to=['to@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Cc'] == 'cc1@example.com, cc2@example.com'
        assert email.recipients() == ['to@example.com', 'cc1@example.com', 'cc2@example.com']
        
        email = EmailMessage('Subject', 'Content', to=['to@example.com'], cc=['cc3@example.com'])
        message = email.message()
        
        assert message['Subject'].encode() == 'Subject'
        assert message.get_payload() == 'Content'
        assert message['From'] == 'root@localhost'
        assert message['To'] == 'to@example.com'
        assert message['Cc'] == 'cc3@example.com, cc1@example.com, cc2@example.com'
        assert email.recipients() == ['to@example.com', 'cc3@example.com', 'cc1@example.com', 'cc2@example.com']
    
    def test_overrides(self):
        """Test overrides"""
        
        self.app.settings.emails.override = 'override@example.com'
        email = EmailMessage('Subject', 'Content', 'from@example.com', ['to@example.com'], cc=['cc@example.com'], bcc=['bcc@example.com'])
        message = email.message()
        email.send()
        assert message['Subject'].encode() == 'Subject'
        assert message['From'] == 'from@example.com'
        assert message['To'] == 'override@example.com'
        assert message['Cc'] == ''
        assert email.recipients() == ['override@example.com']
        
        msg_body = '%s\n\nTo: to@example.com  =\n\nCc: cc@example.com  =\n\nBcc: bcc@example.com\n\n%s\n\nContent' % ('-'*70, '-'*70)
        assert msg_body in message.as_string()
    
    def test_multi_part(self):
        text_content = 'This is an important message.'
        email = EmailMultiAlternatives('Subject', text_content, 'from@example.com', ['to@example.com'], cc=['cc@example.com'], bcc=['bcc@example.com'])
        
        html_content = '<p>This is an <strong>important</strong> message.</p>'
        email.attach_alternative(html_content, "text/html")

        message = email.message()
        text_part = \
r"""Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

This is an important message."""
        html_part = \
r"""Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

<p>This is an <strong>important</strong> message.</p>"""

        text_message = message.as_string()
        assert text_part in text_message
        assert html_part in text_message

    def test_markdown_email(self):
        text_content = 'This is an **important** message.'
        email = MarkdownMessage('Subject', text_content, 'from@example.com', ['to@example.com'], cc=['cc@example.com'], bcc=['bcc@example.com'])
        
        message = email.message()
        text_part = \
r"""Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

This is an **important** message."""
        html_part = \
r"""Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

<p>This is an <strong>important</strong> message.</p>
"""

        text_message = message.as_string()
        assert text_part in text_message
        assert html_part in text_message

    def test_html_email(self):
        body = '<p>This is an <strong>important</strong> message.</p>'
        email = HtmlMessage('Subject', body, 'from@example.com', ['to@example.com'], cc=['cc@example.com'], bcc=['bcc@example.com'])
        
        message = email.message()
        text_part = \
r"""Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

This is an **important** message.
"""
        html_part = \
r"""Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

<p>This is an <strong>important</strong> message.</p>
"""

        text_message = message.as_string()
        assert text_part in text_message
        assert html_part in text_message
    
    def test_html_overrides(self):
        """Test overrides with html content"""
        
        self.app.settings.emails.override = 'override@example.com'
        body = '<p>This is an <strong>important</strong> message.</p>'
        email = EmailMessage('Subject', body, 'from@example.com', ['to@example.com'], cc=['cc@example.com'], bcc=['bcc@example.com'])
        email.content_subtype = "html"  # Main content is now text/html
        message = email.message()
        
        msg_body = '<hr />\n\n<p>To: to@example.com <br />\nCc: cc@example.com <br />\nBcc: bcc@example.com</p>\n\n<hr />\n<p>This is an <strong>important</strong> message.</p>'
        assert msg_body in message.as_string()
        assert 'text/html;' in message['Content-Type']
    
    def test_html_override_with_full_document(self):
        html_doc = r"""<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
    <title>Minimal XHTML 1.0 Document with W3C DTD</title>
  </head>
  <body>
    <p>This is a minimal <a href="http://www.w3.org/TR/xhtml1/">XHTML 1.0</a> 
    document with a W3C url for the DTD.</p>
  </body>
</html>"""
        self.app.settings.emails.override = 'override@example.com'
        email = EmailMessage('Subject', html_doc, 'from@example.com', ['to@example.com'], cc=['cc@example.com'], bcc=['bcc@example.com'])
        email.content_subtype = "html"  # Main content is now text/html
        message = email.message()
        
        msg_body = '<body><hr />\n\n<p>To: to@example.com <br />\nCc: cc@example.com <br />\nBcc: bcc@example.com</p>\n\n<hr />\n\n    <p>This is a minimal '
        assert msg_body in message.as_string()
        assert 'text/html;' in message['Content-Type']

    def test_multipart_html_override_with_full_document(self):
        html_doc = r"""<!DOCTYPE html 
     PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
  <head>
    <title>Minimal XHTML 1.0 Document with W3C DTD</title>
  </head>
  <body>
    <p>This is a minimal <a href="http://www.w3.org/TR/xhtml1/">XHTML 1.0</a> 
    document with a W3C url for the DTD.</p>
  </body>
</html>"""
        self.app.settings.emails.override = _to
        email = HtmlMessage('Subject', html_doc, 'from@example.com', ['to@example.com'])
        message = email.message()
        
        msg_body = '<body><hr />\n\n<p>To: to@example.com\nCc: cc@example.com\nBcc: bcc@example.com</p>\n\n<hr />\n\n    <p>This is a minimal '
        text_part = \
r"""Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

----------------------------------------------------------------------

To: to@example.com  =

Cc:   =

Bcc: =


----------------------------------------------------------------------

This is a minimal [XHTML 1.0][1] document with a W3C url for the DTD.
   [1]: http://www.w3.org/TR/xhtml1/
"""
        html_part = \
r"""</head>
  <body><hr />

<p>To: to@example.com <br />
Cc: <br />
Bcc: </p>

<hr />

    <p>This is a minimal"""

        text_message = message.as_string()
        assert text_part in text_message
        assert html_part in text_message
        
        if _send_live:
            email.send()

    def test_send_mail(self):
        if _send_live:
            send_mail('test text email', 'email content', [_to])
            
            send_mail('test markdown email', '**important** email content', [_to], 'markdown')
            
    def tearDown(self):
        self.app = None
        rcm.cleanup()
        
if __name__ == '__main__':
    unittest.main()
