import os
from datetime import datetime
import uuid
import json

import boto3
import mailparser

from leadParser import LeadParser, RightbizParser, DaltonsParser, HomecareParser, B4sParser, NdaParser

region_name = os.getenv('region_name') or 'eu-west-2'
aws_access_key_id = os.getenv('aws_access_key_id')
aws_secret_access_key = os.getenv('aws_secret_access_key')
aws_s3_bucket = os.getenv('aws_s3_bucket') or 'adminify-fr'
queue_url_franchise_resales_lead_create_or_update = os.getenv('queue_url_franchise_resales_lead_create_or_update')  or 'https://sqs.eu-west-2.amazonaws.com/420219040634/franchiseResalesFreshsalesLeadCreateOrUpdate.fifo'



s3_client = boto3.client('s3',
                        region_name=region_name,
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key
                        )

def lambda_handler(event, context):

    objects = s3_client.list_objects_v2(Bucket=aws_s3_bucket)

    lp = LeadParser()
    rbp = RightbizParser()
    dp = DaltonsParser()
    hcp = HomecareParser()
    b4s = B4sParser()
    nda = NdaParser()

    if not objects.get('Contents'):
        print('Nothing to process')
        return {
            'statusCode': 200,
            'body': json.dumps({'Message': 'No Leads to process...'})
        }

    leads_to_upload = []

    def delete_object(object_key):
        deleted_lead = s3_client.delete_object(Bucket=aws_s3_bucket, Key=object_key)
        print(deleted_lead) 

    for obj in objects['Contents']:

        data = s3_client.get_object(Bucket=aws_s3_bucket, Key=obj['Key'])
        mail = mailparser.parse_from_bytes(data['Body'].read()) 

        lead_source = lp.get_lead_source(mail.text_plain)
        print(mail.text_plain)

        if lead_source == 'rightbiz':
            enquiry_payload = rbp.get_contact_payload(mail.text_plain, mail.date)
            if len(enquiry_payload['email']) > 0:
                # print(enquiry_payload)
                enquiry_payload['obj_key'] = obj['Key']
                leads_to_upload.append(enquiry_payload)
                delete_object(obj['Key'])
            else:
                print('No data to parse - RB')
                delete_object(obj['Key'])

        elif lead_source == 'daltons':
            enquiry_payload = dp.get_contact_payload(mail.text_plain, mail.date)
            if len(enquiry_payload['email']) > 0:
                # print(enquiry_payload)
                enquiry_payload['obj_key'] = obj['Key']
                leads_to_upload.append(enquiry_payload)
                delete_object(obj['Key'])
            else:
                print('No data to parse - DAL')
                delete_object(obj['Key'])

        elif lead_source == 'homecare':
            enquiry_payload = hcp.get_contact_payload(mail.text_plain, mail.date)
            if len(enquiry_payload['email']) > 0:
                # print(enquiry_payload)
                enquiry_payload['obj_key'] = obj['Key']
                leads_to_upload.append(enquiry_payload)
                delete_object(obj['Key'])
            else:
                print('No data to parse - HC')
                delete_object(obj['Key'])

        elif lead_source == 'b4s':
            enquiry_payload = b4s.get_contact_payload(mail.text_plain, mail.date)
            if len(enquiry_payload['email']) > 0:
                # print(enquiry_payload)
                enquiry_payload['obj_key'] = obj['Key']
                leads_to_upload.append(enquiry_payload)
                delete_object(obj['Key'])
            else:
                print('No data to parse - B4S')
                delete_object(obj['Key'])

        #elif lead_source == 'nda':
        #    enquiry_payload = nda.get_contact_payload(mail.text_plain, mail.date)
        #    if len(enquiry_payload['email']) > 0:
        #        enquiry_payload['nda_file'] = nda.get_attachment_payload(mail.attachments)
        #        enquiry_payload['obj_key'] = obj['Key']
        #        # print(enquiry_payload)
        #        leads_to_upload.append(enquiry_payload)
        #    else:
        #        print('No data to parse - NDA')
        #        delete_object(obj['Key'])

        # elif lead_source == 'registerinterest':
        #     print('TODO: Franchise Resales Mailing List')

        else:
            print(mail.text_plain)
            print('No parser for data source')
            delete_object(obj['Key'])

    # Create SQS client
    sqs = boto3.client(
        'sqs',
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )

    for lead in leads_to_upload:

        payload = lead
        # Send message to SQS queue
        response = sqs.send_message(
            QueueUrl=queue_url_franchise_resales_lead_create_or_update,
            MessageBody=(
                json.dumps(payload)
            ),
            MessageAttributes={
            },
            MessageGroupId = str(uuid.uuid4().hex)
        )

        print(lead)
        # delete_object(obj['Key'])

    return {
        'statusCode': 200,
        'body': json.dumps({'Message': 'Leads Processed', 'lead_list': leads_to_upload})
    }
    
