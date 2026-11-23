import json
import os
import urllib.error
import urllib.request
from email.utils import parseaddr
from django.core.mail.backends.base import BaseEmailBackend


class SendGridAPIBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = os.environ.get('SENDGRID_API_KEY', '').strip()
        if not api_key:
            print("[SENDGRID] ERROR: Falta la variable SENDGRID_API_KEY en Render.")
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                from_name, from_addr = parseaddr(
                    message.from_email or os.environ.get('DEFAULT_FROM_EMAIL', '')
                )
                from_obj = {'email': from_addr}
                if from_name:
                    from_obj['name'] = from_name

                personalization = {'to': [{'email': addr} for addr in message.to]}
                if getattr(message, 'cc', None):
                    personalization['cc'] = [{'email': addr} for addr in message.cc]
                if getattr(message, 'bcc', None):
                    personalization['bcc'] = [{'email': addr} for addr in message.bcc]

                content = [{'type': 'text/plain', 'value': message.body or ' '}]
                for alt_content, alt_mimetype in getattr(message, 'alternatives', []):
                    if alt_mimetype == 'text/html':
                        content.append({'type': 'text/html', 'value': alt_content})

                payload = {
                    'personalizations': [personalization],
                    'from': from_obj,
                    'subject': message.subject or '(Sin asunto)',
                    'content': content,
                }
                if getattr(message, 'reply_to', None):
                    _, r_addr = parseaddr(message.reply_to[0])
                    if r_addr:
                        payload['reply_to'] = {'email': r_addr}

                req = urllib.request.Request(
                    'https://api.sendgrid.com/v3/mail/send',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json',
                    },
                    method='POST',
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    print(f"[SENDGRID] OK ({resp.status}) enviado a {message.to} desde {from_addr}")
                    sent_count += 1
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='replace')
                print(f"[SENDGRID] HTTP ERROR {e.code}: {err_body}")
                if not self.fail_silently:
                    raise
            except Exception as e:
                print(f"[SENDGRID] ERROR: {e}")
                if not self.fail_silently:
                    raise
        return sent_count
