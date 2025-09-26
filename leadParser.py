from datetime import datetime
import re
import base64

class LeadParser:
    def __init__(self, email_body=None):
        self.email_body = email_body

    def get_all_email_addresses(self, email_body):
        return set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email_body))
    
    def flatten(xss):
        return set([x for xs in xss for x in xs])

    def get_lead_source(self, email_body):
        for part in email_body:
            if '@daltonssupportmail.com' in part:
                return 'daltons'
            elif '@rightbiz.co.uk' in part:
                return 'rightbiz'
            elif '@homecare.co.uk' in part:
                return 'homecare'
            elif '@BusinessesForSale.com' in part:
                return 'b4s'
            elif 'Register my interest' in part:
                return 'registerinterest'
            elif 'NDA Submission' in part:
                return 'nda'
            else:
                return None

class RightbizParser:
    def __init__(self, email_body=None):
        self.email_body = email_body

    def get_contact_payload(self, email_body, email_date=''):
        contact = {
            'lead_source': 'rightbiz',
            'resale_reference': '',
            'first_name': '',
            'last_name': '',
            'email': '',
            'telephone': ''
        }

        for part in email_body:
            for line in part.splitlines():

                line = line.replace('*', '')

                if line.startswith('Ref:'):
                    reference = line.split(':') # split into key and value
                    contact['resale_reference'] = reference[1].split()[0].strip()

                if line.startswith('Name'):
                    full_name = line.split(':') # split into key and value
                    contact['first_name'] = full_name[1].split()[0].strip().title()
                    contact['last_name'] = full_name[1].split()[-1].strip().title()

                if line.startswith('Email'):
                    email = line.split(':', 1) # split into key and value
                    contact['email'] = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1])[0] if re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1]) else ''

                if line.startswith('Ref:'):
                    reference = line.split(':') # split into key and value
                    contact['resale_reference'] = reference[1].strip()

                if line.startswith('Telephone:'):
                    telephone = line.split(':', 1) # split into key and value
                    contact['telephone'] = telephone[1].strip()

                elif 'Telephone Number:' in line:
                    telephone = line.rsplit(':', 1) # split into key and value
                    contact['telephone'] = telephone[1].strip()

                if line.startswith('Mobile:'):
                    mobile = line.split(':') # split into key and value
                    contact['mobile'] = mobile[1].strip()

        contact['receipt_date'] = email_date.strftime("%Y-%m-%dT%H:%M:%S%Z")

        return contact


class DaltonsParser:
    def __init__(self, email_body=None):
        self.email_body = email_body

    def get_contact_payload(self, email_body, email_date=''):
        contact = {
            'lead_source': 'daltons',
            'resale_reference': '',
            'first_name': '',
            'last_name': '',
            'email': '',
            'telephone': ''
        }

        for part in email_body:
            for line in part.splitlines():

                if line.startswith('More Details are required for business with reference: '):
                    reference = line.split(':') # split into key and value
                    contact['resale_reference'] = reference[1].split()[0].strip()

                if line.startswith('Contact details:- Name :'):
                    full_name = line.split(':')[1:] # split into key and value
                    contact['first_name'] = full_name[1].split()[0].strip().title()
                    contact['last_name'] = full_name[1].split()[-1].strip().title()

                if line.startswith('Email Address :'):
                    email = line.split(':') # split into key and value
                    contact['email'] = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1])[0] if re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1]) else ''

                if line.startswith('Contact Phone :'):
                    telephone = line.split(':') # split into key and value
                    contact['telephone'] = telephone[1].strip()

        contact['receipt_date'] = email_date.strftime("%Y-%m-%dT%H:%M:%S%Z")

        return contact

class HomecareParser:
    def __init__(self, email_body=None):
        self.email_body = email_body

    def get_contact_payload(self, email_body, email_date=''):
        contact = {
            'lead_source': 'homecare',
            'resale_reference': '',
            'first_name': '',
            'last_name': '',
            'email': '',
            'telephone': ''
        }

        for part in email_body:
            for line in part.splitlines():

                if line.startswith('Your Reference: '):
                    reference = line.split(':') # split into key and value
                    contact['resale_reference'] = reference[1].split()[0].strip()

                if line.startswith('First Name:'):
                    contact['first_name'] = line.split(':')[-1].strip().title()

                if line.startswith('Last Name:'):
                    contact['last_name'] = line.split(':')[-1].strip().title()

                if line.startswith('Email Address:'):
                    email = line.split(':') # split into key and value
                    contact['email'] = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1])[0] if re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1]) else ''

                if line.startswith('Telephone Number:'):
                    telephone = line.split(':') # split into key and value
                    contact['telephone'] = telephone[1].strip()

        contact['receipt_date'] = email_date.strftime("%Y-%m-%dT%H:%M:%S%Z")

        return contact


class B4sParser:
    def __init__(self, email_body=None):
        self.email_body = email_body

    def get_contact_payload(self, email_body, email_date=''):
        contact = {
            'lead_source': 'businesses for sale',
            'resale_reference': '',
            'first_name': '',
            'last_name': '',
            'email': '',
            'telephone': ''
        }

        for part in email_body:
            for line in part.splitlines():
                if line.startswith('Your Reference:'):
                    reference = line.split(':') # split into key and value
                    contact['resale_reference'] = reference[1].split()[0].strip()

                if line.startswith('Your listing ref:'):
                    reference = line.split(':') # split into key and value
                    contact['resale_reference'] = reference[1].split()[0].strip()

                if line.startswith('Name:'):
                    full_name = line.split(':') # split into key and value
                    contact['first_name'] = full_name[1].split()[0].strip().title()
                    contact['last_name'] = full_name[1].split()[-1].strip().title()

                if line.startswith('Email:'):
                    email = line.split(':') # split into key and value
                    contact['email'] = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1])[0] if re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', email[-1]) else ''

                if line.startswith('Telephone Number:'):
                    telephone = line.split(':') # split into key and value
                    contact['telephone'] = telephone[1].strip()

                if line.startswith('Tel:'):
                    telephone = line.split(':') # split into key and value
                    contact['telephone'] = telephone[1].strip()

                if line.startswith('Phone Number:'):
                    telephone = line.split(':') # split into key and value
                    contact['telephone'] = telephone[1].strip()

        contact['receipt_date'] = email_date.strftime("%Y-%m-%dT%H:%M:%S%Z")

        return contact


class NdaParser:
    def __init__(self, email_body=None):
        self.email_body = email_body

    def get_contact_payload(self, email_body, email_date=''):
        contact = {
            'lead_source': 'nda',
            'resale_reference': '',
            'first_name': '',
            'last_name': '',
            'email': '',
            'telephone': ''
        }

        for part in email_body:
            part_split = part.split('Email:')
            contact['email'] = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', part_split[1])[0] if re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', part_split[1]) else ''
        contact['nda_file'] = []
        
        contact['receipt_date'] = email_date.strftime("%Y-%m-%dT%H:%M:%S%Z")

        return contact

    def get_attachment_payload(self, attachments=None):
        attachment_base64_list = []
        for attachment in attachments:
            # print(attachment)
            if attachment['mail_content_type'] == 'application/pdf':
                filename = re.findall(r'"([^"]*)"', attachment['content-disposition'])[0]
                file_data = attachment['payload']
                # if attachment['binary']:
                    # file_data = base64.b64decode(attachment['payload'])
                    # with open(filename, "wb") as f:
                    #     f.write(base64.b64decode(attachment['payload']))
                # else:
                    # file_data = attachment['payload']
                    # with open(filename, "w") as f:
                    #     f.write(attachment['payload'])
                attachment_base64_list.append({'filename': filename, 'file_data': file_data})
        return attachment_base64_list
        
