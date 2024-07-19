from fastapi import FastAPI, HTTPException, Response, status
import boto3
import logging
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
import base64

from schemas import ItemCreate, ItemUpdate

load_dotenv()

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region = os.getenv('REGION')

rekognition_client = boto3.client('rekognition',
                                 aws_access_key_id=aws_access_key_id,
                                 aws_secret_access_key=aws_secret_access_key,
                                 region_name=region
                                 )

dynamodb_table_name = os.getenv('DYNAMO_TABLE_NAME')
dynamodb = boto3.resource('dynamodb', region)
faceid_table = dynamodb.Table(dynamodb_table_name)

app = FastAPI()


@app.post("/create/")
def create_item(item: ItemCreate, response: Response):
    if item.base64:
        base_64_decoded = base64.b64decode(item.base64)
        rekognition_response = rekognition_client.detect_faces(
            Image={
                'Bytes': base_64_decoded
            },
            Attributes=['ALL']
        )
        if rekognition_response['FaceDetails']:
            rekognition_index_response = rekognition_client.index_faces(
                CollectionId=os.getenv('COLLECTION_ID'),
                Image={
                    'Bytes': base_64_decoded
                },
                ExternalImageId=f'{item.developerId}-{item.clientUserId}',
                DetectionAttributes=['ALL']
            )
            face_id = rekognition_index_response['FaceRecords'][0]['Face']['FaceId']
            faceid_table.put_item(
                Item={
                    'faceId': face_id,
                    'developerId': item.developerId,
                    'clientUserId': item.clientUserId
                }
            )
            response.status_code = status.HTTP_201_CREATED
            return {
                'faceId': face_id,
            }
        else:
            return "No faces detected in the image."

    else:
        return "O base64 é necessario para fazer o registro do usuário"

@app.put("/update/{face_id}")
def update_item(face_id: str, item: ItemUpdate):

    old_item = faceid_table.get_item(
        Key={
            'faceId': face_id,
        }
    )
    old_item_response = old_item.get('Item')

    if not old_item_response:
        raise HTTPException(status_code=404, detail={"status": "Failure", "error": f"User {face_id} does not exist"})

    if item.base64: # TODO arrumar o old item
        base_64_decoded = base64.b64decode(item.base64)
        rekognition_response = rekognition_client.detect_faces(
            Image={
                'Bytes': base_64_decoded
            },
            Attributes=['ALL']
        )
        if rekognition_response['FaceDetails']:
            rekognition_index_response = rekognition_client.index_faces(
                CollectionId=os.getenv('COLLECTION_ID'),
                Image={
                    'Bytes': base_64_decoded
                },
                ExternalImageId=str(face_id),
                DetectionAttributes=['ALL']
            )

            new_face_id = rekognition_index_response['FaceRecords'][0]['Face']['FaceId']

            faceid_table.delete_item(Key={'faceId': face_id})
            rekognition_client.delete_faces(CollectionId=os.getenv('COLLECTION_ID'), FaceIds=[face_id])
            
            try:
                faceid_table.put_item(
                    Item={
                        'faceId': new_face_id,
                        'developerId': int(old_item['Item']['developerId']),
                        'clientUserId': old_item['Item']['clientUserId']
                    }
                )

            except ClientError as e:
                logging.error(e)
                raise HTTPException(status_code=500, detail={"status": "Failure", "error": "Could not update the user"})

            return {'faceId': new_face_id}

@app.delete("/delete/{face_id}")
def delete_item(face_id: str):
    try:
        faceid_table.delete_item(Key={'faceId': face_id})
        delete_rekog = rekognition_client.delete_faces(CollectionId=os.getenv('COLLECTION_ID'), FaceIds=[face_id])

        delete_rekog_response = delete_rekog.get('DeletedFaces')

        if not delete_rekog_response:
            raise HTTPException(status_code=404, detail={"status": "Failure", "error": f"User {face_id} does not exist"})

        return {"details": {"status": "Success", "body": 'User deleted'}}
    except ClientError as e:
        logging.error(e)
        raise HTTPException(status_code=500, detail={"status": "Failure", "error": "Could not delete the user, try again later"})
