from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import os
import json

app = FastAPI()
BACKUP_DIR = '/backups'
os.makedirs(BACKUP_DIR, exist_ok=True)

class BackupPayload(BaseModel):
    account_id: int
    data: dict

@app.get('/health')
def health():
    return {'status': 'ok', 'version': '1.0.0', 'timestamp': 1777507223.254}

@app.get('/')
def root():
    return {
        'service': 'TeleBot Backend',
        'version': '1.0.0',
        'endpoints': [
            '/health',
            '/backup/import',
            '/backup/import_json',
            '/mtproto/login',
            '/phone/generate',
            '/phone/validate',
            '/phone/list',
            '/sms/send',
            '/sms/list',
        ]
    }

@app.post('/backup/import')
async def import_backup(file: UploadFile = File(...)):
    path = os.path.join(BACKUP_DIR, file.filename)
    with open(path, 'wb') as f:
        content = await file.read()
        f.write(content)
    return {'status': 'saved', 'path': path}

@app.post('/backup/import_json')
async def import_backup_json(payload: BackupPayload):
    path = os.path.join(BACKUP_DIR, f'backup_{payload.account_id}.json')
    with open(path, 'w') as f:
        json.dump(payload.data, f)
    return {'status': 'saved', 'path': path}

@app.post('/mtproto/login')
async def mtproto_login(api_id: int, api_hash: str, phone: str, password: str | None = None):
    return {'status': 'not_implemented', 'message': 'MTProto login requires integration with Telegram libraries'}

import random
import time
from typing import Optional, List

phone_numbers_db = []
sms_records_db = []

class PhoneGenerateRequest(BaseModel):
    count: int = 1

def generate_hk_number():
    prefixes = ['5', '6', '9']
    prefix = random.choice(prefixes)
    number = ''.join([str(random.randint(0, 9)) for _ in range(7)])
    return f"+852{prefix}{number}"

@app.post('/phone/generate')
def generate_phone(request: PhoneGenerateRequest):
    if request.count < 1 or request.count > 100:
        request.count = 10
    generated = []
    for i in range(request.count):
        phone_id = len(phone_numbers_db) + i + 1
        phone = generate_hk_number()
        phone_numbers_db.append({
            'id': phone_id, 'number': phone, 'country': 'HK',
            'status': 'generated', 'is_valid': False
        })
        generated.append({'id': phone_id, 'number': phone, 'country': 'HK', 'status': 'generated'})
    return {'message': '生成成功', 'data': generated, 'count': len(generated)}

class ValidatePhoneRequest(BaseModel):
    numbers: List[str]

@app.post('/phone/validate')
def validate_phone(request: ValidatePhoneRequest):
    results = []
    for num in request.numbers:
        is_valid = len(num) == 11 and num.startswith('+852') and num[3] in '569'
        results.append({'number': num, 'is_valid': is_valid, 'status': 'valid' if is_valid else 'invalid'})
    return {'data': results}

@app.get('/phone/list')
def list_phones(status: Optional[str] = None):
    phones = phone_numbers_db
    if status:
        phones = [p for p in phones if p['status'] == status]
    return {'data': phones, 'total': len(phones)}

class SendSMSRequest(BaseModel):
    phone: str
    content: str
    sender: str = "TelegramBot"

@app.post('/sms/send')
def send_sms(request: SendSMSRequest):
    phone = request.phone
    if len(phone) == 9:
        phone = f"+852{phone}"
    print(f"[SMS] 发送短信到 {phone}: {request.content}")
    sms_id = len(sms_records_db) + 1
    sms_records_db.append({
        'id': sms_id, 'phone': phone, 'content': request.content,
        'sender': request.sender, 'status': 'sent'
    })
    return {'message': '发送成功', 'sms_id': sms_id, 'phone': phone, 'status': 'sent'}

@app.get('/sms/list')
def list_sms():
    return {'data': sms_records_db, 'total': len(sms_records_db)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)