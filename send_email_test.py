from __future__ import print_function

from twisted.mail.smtp import sendmail
from twisted.internet.task import react

from email.mime.text import MIMEText

def main(reactor):
    me = "chetan@packetservo.com"
    to = "chetanbnaik@gmail.com"

    message = MIMEText("This is my super awesome email, sent with Twisted!")
    message["Subject"] = "Twisted is great!"
    message["From"] = me
    message["To"] = to

    d = sendmail("smtp.gmail.com", me, to, message,
                 port=587, username=me, password="Hyus2dXC1",
                 requireAuthentication=True,
                 requireTransportSecurity=True)

    d.addBoth(print)
    return d

react(main)
