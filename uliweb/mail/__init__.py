#######################################
#
# Send mail
# Known smtp server: smtp.gmail.com, 587
#######################################
import os
import smtplib
import mimetypes
import email
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.MIMEAudio import MIMEAudio
from email.MIMEImage import MIMEImage
from email.Encoders import encode_base64
from email.header import Header

class BaseMailConnection(object):
    def __init__(self, mail_obj):
        self.mail_obj = self.mail_obj
        
    def get_connection(self, mail_obj):
        raise NotImplementedError, "This function is not implemented yet"

    def send_mail(self, from_, to_, message):
        raise NotImplementedError, "This function is not implemented yet"
    
    def close(self):
        pass
   
class EmailMessage(object):
    def __init__(self, from_, to_, subject, message, html=False, encoding='utf-8', attachments=None):
        from uliweb.utils.common import simple_value
        
        self.from_ = from_
        self.to_ = to_
        self.encoding = encoding
        self.subject = simple_value(subject, encoding)
        self.message = simple_value(message, encoding)
        self.attachments = attachments or []
        self.html = html
        
        self.msg = msg = MIMEMultipart()
        msg['From'] = from_
        msg['To'] = to_
        msg['Subject'] = Header(self.subject, self.encoding)
        if html:
            content_type = 'html'
        else:
            content_type = 'plain'
        msg.attach(MIMEText(self.message, content_type, self.encoding))
        
        for f in attachments:
            msg.attach(self.getAttachment(f))
            
    def attach(self, filename):
        self.msg.attach(self.getAttachment(filename))
        
    def getAttachment(self, attachmentFilePath):
        contentType, encoding = mimetypes.guess_type(attachmentFilePath)
        if contentType is None or encoding is not None:
            contentType = 'application/octet-stream'
        mainType, subType = contentType.split('/', 1)
        file = open(attachmentFilePath, 'rb')
        if mainType == 'text':
            attachment = MIMEText(file.read())
#        elif mainType == 'html':
#            attachment = MIMEText(file.read(), 'html')
        elif mainType == 'message':
            attachment = email.message_from_file(file)
        elif mainType == 'image':
            attachment = MIMEImage(file.read(),_subType=subType)
        elif mainType == 'audio':
            attachment = MIMEAudio(file.read(),_subType=subType)
        else:
            attachment = MIMEBase(mainType, subType)
            attachment.set_payload(file.read())
            encode_base64(attachment)
        file.close()
        attachment.add_header('Content-Disposition', 'attachment',   filename=os.path.basename(attachmentFilePath))
        return attachment
    
    def __str__(self):
        return self.msg.as_string()
        
class Mail(object):
    def __init__(self):
        from uliweb import settings
        from uliweb.utils.common import import_attr
        
        self.host = settings.MAIL.HOST
        self.port = settings.MAIL.PORT
        self.user = settings.MAIL.USER
        self.password = settings.MAIL.PASSWORD
        self.backend = settings.MAIL.BACKEND or 'uliweb.mail.backends.smtp'
        cls = import_attr(self.backend + '.MailConnection')
        self.con = cls(self)
        
    def send_mail(self, from_, to_, subject, message, html=False, attachments=None):
        email = EmailMessage(from_, to_, subject, message, html=html, attachments=attachments)
        self.con.get_connection()
        self.con.send_mail(from_, to_, email)
        self.con.close()
        