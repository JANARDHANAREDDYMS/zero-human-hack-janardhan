"""Whop Standard Webhooks signatures, using literal secret bytes including prefix.

Matches the official Whop SDK's verify_webhook._hmac_key behavior: unlike
standardwebhooks' generic whsec convention, Whop does not decode its secret.
"""
import base64,hashlib,hmac,json,time

class SignatureError(ValueError):pass

def verify(body,headers,secret,*,now=None):
    h={k.lower():v for k,v in headers.items()}
    message_id=h.get('webhook-id','');timestamp=h.get('webhook-timestamp','');signatures=h.get('webhook-signature','')
    if not secret or not message_id or len(message_id)>200 or len(signatures)>4000:raise SignatureError('Invalid webhook signature')
    try:stamp=int(timestamp)
    except (TypeError,ValueError):raise SignatureError('Invalid webhook timestamp') from None
    if abs((time.time() if now is None else now)-stamp)>300:raise SignatureError('Expired webhook timestamp')
    expected=base64.b64encode(hmac.new(secret.encode(),message_id.encode()+b'.'+timestamp.encode()+b'.'+body,hashlib.sha256).digest()).decode()
    if not any(part.startswith('v1,') and hmac.compare_digest(part[3:],expected) for part in signatures.split()):raise SignatureError('Invalid webhook signature')
    try:event=json.loads(body)
    except (ValueError,UnicodeError):raise ValueError('Invalid webhook JSON') from None
    if not isinstance(event,dict) or event.get('id')!=message_id:raise ValueError('Webhook ID mismatch')
    return event
