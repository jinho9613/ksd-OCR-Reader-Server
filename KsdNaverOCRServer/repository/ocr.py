import sqlalchemy
from fastapi import HTTPException, status, Response
from sqlalchemy.orm import Session

from KsdNaverOCRServer.models import ocr as ocr_models
from KsdNaverOCRServer.models import user as user_models
from KsdNaverOCRServer.schemas import ocr as ocr_schemas

import requests
import time
import json, os

from KsdNaverOCRServer.resources.naver_ocr_domain_key import NAVER_OCR_DOMAIN_KEY as ocr_keys

RESULT_FILE = os.getcwd() + "/result/"


def ocr_request(request: ocr_schemas.RequestOCR):
    selected_ocr = ocr_keys[0]
    for ocr_key in ocr_keys:
        if ocr_key['category'] == request.ocr_type:
            selected_ocr = ocr_key
    request_json = {
        'images': [
            {
                'format': request.s3_url.split('.')[-1],
                'name': 'image',
                'url': request.s3_url
            }
        ],
        'requestId': 'ocr-request',
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }

    payload = json.dumps(request_json).encode('UTF-8')
    headers = {
        'X-OCR-SECRET': selected_ocr['secret_key'],
        'Content-Type': 'application/json'
    }

    response = requests.post(url=selected_ocr['APIGW_Invoke_url'], headers=headers, data=payload)
    # print_result_on_terminal(response)
    return json.loads(response.text)


# Terminal Test용
def print_result_on_terminal(response):
    dict_data = json.loads(response.text)
    if dict_data['images'][0]['inferResult'] == 'SUCCESS':
        result = []
        for field in dict_data['images'][0]['fields']:
            result.append({
                # 'name': field['name'],
                # 'inferText': field['inferText']
                field['name']: field['inferText']
            })
    result_dict = {
        'template_name': dict_data['images'][0]['matchedTemplate']['name'],
        'results': result
    }
    from pprint import pprint
    pprint(result_dict)


# User Id를 추가한 요청
def ocr_request_by_user(request: ocr_schemas.RequestOCRByUser, db: Session):
    # Check User Exist
    user = db.query(user_models.User).filter(user_models.User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'User with id {request.user_id} not found')

    selected_ocr = ocr_keys[0]
    for ocr_key in ocr_keys:
        if ocr_key['category'] == request.ocr_type:
            selected_ocr = ocr_key
    request_json = {
        'images': [
            {
                'format': request.s3_url.split('.')[-1],
                'name': 'image',
                'url': request.s3_url
            }
        ],
        'requestId': 'ocr-request',
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }

    payload = json.dumps(request_json).encode('UTF-8')
    headers = {
        'X-OCR-SECRET': selected_ocr['secret_key'],
        'Content-Type': 'application/json'
    }

    response = requests.post(url=selected_ocr['APIGW_Invoke_url'], headers=headers, data=payload)

    # save result by user
    file_name = f"""{request.user_id}-{json.loads(response.text)['timestamp']}.json"""
    with open(RESULT_FILE + file_name, "w+") as json_file:
        json.dump(json.loads(response.text), json_file)

    new_ocr_result = ocr_models.OcrResult(user_id=user.id, result_file_name=file_name)
    db.add(new_ocr_result)
    db.commit()

    result = json.loads(response.text)
    result['id'] = new_ocr_result.id
    return result


# 결과 받기
def get_ocr_result_by_OCR_ID(ocr_id: int, db: Session):
    ocr_result = db.query(ocr_models.OcrResult).filter(ocr_models.OcrResult.id == ocr_id).first()
    if not ocr_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'OCR Result with id {ocr_id} not found')

    with open(RESULT_FILE + ocr_result.result_file_name, "r") as json_file:
        result = json.load(json_file)

    return result


def get_ocr_result_by_user(user_id: int, db: Session):
    result = []

    # Check User Exist
    user = db.query(user_models.User).filter(user_models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'User with id {user_id} not found')

    ocr_results = db.query(ocr_models.OcrResult).filter(ocr_models.OcrResult.user_id == user_id)
    if not ocr_results.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'OCR Result not found')

    for ocr_result in ocr_results.all():
        with open(RESULT_FILE + ocr_result.result_file_name, "r") as json_file:
            result_append = json.load(json_file)
            result_append['id'] = ocr_result.id
            result.append(result_append)
    return result


def get_ocr_result_all(db: Session):
    result = []
    ocr_results = db.query(ocr_models.OcrResult).filter()
    if not ocr_results.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'OCR Result not found')
    for ocr_result in ocr_results.all():
        with open(RESULT_FILE + ocr_result.result_file_name, "r") as json_file:
            result_append = json.load(json_file)
            result_append['id'] = ocr_result.id
            result.append(result_append)
    return result


def delete_ocr_result(ocr_id: int, db: Session):
    ocr_result = db.query(ocr_models.OcrResult).filter(ocr_models.OcrResult.id == ocr_id)
    if not ocr_result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'OCR Result not found')
    file_name = ocr_result.first().result_file_name
    ocr_result.delete()
    db.commit()
    os.remove(RESULT_FILE + file_name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)