import logging
import httplib2
import os
import redisqueue as qm

from googleapiclient.http import MediaFileUpload
from datetime import datetime, timedelta
from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'CCTV'
APP_FOLDER_TYPE = 'application/vnd.google-apps.folder'
DEFAULT_BEFORE_DAYS = 7

# SECTION : AUTHORIZATION
try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None


class GoogleDrive(object):

    def __init__(self, redis):
        self.redis = redis
        self.drive_service = self.get_service_object()

    def get_credentials(self):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        Returns:
            Credentials, the obtained credential.
        """
        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.credentials')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir,
                                       'drive-python-quickstart.json')

        store = Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else: # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)
            logging.info('Storing credentials to ' + credential_path)
        return credentials


    def get_service_object(self):
        credentials = self.get_credentials()
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('drive', 'v3', http=http)
        return service


    # SECTION : Folder manager
    def delete_file(self, file_id):
        try:
            self.drive_service.files().delete(fileId=file_id).execute()
            return True
        except:
            return False


    def find_decay(self, before_days=DEFAULT_BEFORE_DAYS):
        logging.debug("ENTRY - findDecay")
        
        st = datetime.now() - timedelta(days=15)
        query = " modifiedTime <= '" + st.isoformat() + "' and  '" + self.create_folder_if_not_exists(self.drive_service) + "' in parents"
        
        # logging.info(query)
        
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            pageSize=1000,
            fields="nextPageToken, files(id, name)").execute()
        
        items = results.get('files', [])
        
        for item in items:
            # logging.info('{0} ({1})'.format(item['name'], item['id']))
            qm.add_to_deleted_queue(redis=self.redis, element=item['id'])

        logging.debug("EXIT - findDecay")


    def create_folder_if_not_exists(self):
        try:
            results = self.drive_service.files().list(
                q="name='" + APPLICATION_NAME + "' and mimeType='" + APP_FOLDER_TYPE + "'",
                spaces='drive',
                pageSize=10,
                fields="nextPageToken, files(id, name)").execute()
            
            items = results.get('files', [])
            
            if not items:
                # logging.debug('No files found.')
                return self.createFolder()
            else:
                # logging.debug( '{0} ({1})'.format(items[0]['name'], items[0]['id']) )
                return True, items[0]['id']
                # logging.debug('Files:')
                # for item in items:
                #     logging.debug('{0} ({1})'.format(item['name'], item['id']))
        except:
            return False, 0


    def createFolder(self):
        try:
            file_metadata = {
                'name': APPLICATION_NAME,
                'mimeType': APP_FOLDER_TYPE
            }
            
            file = self.drive_service.files().create(body=file_metadata,
                                                fields='id').execute()
            
            # logging.debug ('Folder ID: %s' % file.get('id'))
            
            return True, file.get('id')
        except:
            return False, 0


    def upload_file(self, file_name, file_path):
        try:
            status, folder_id = self.create_folder_if_not_exists()
            if status is True:
                file_metadata = {
                    'name': file_name,
                    'parents': [folder_id]
                }

                media = MediaFileUpload(file_path,
                                        resumable=True)

                file = self.drive_service.files().create(body=file_metadata,
                                                    media_body=media,
                                                    fields='id').execute()

                # logging.debug('File ID: %s' % file.get('id'))
                return True
            else:
                return False
        except Exception as err:
            print('error uploading file')
            return False

        # TODO : List files in a folder

        # TODO : Delete files from a folder

