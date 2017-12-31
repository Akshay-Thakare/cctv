import logging
from googledrive import GoogleDrive
import redisqueue as qm
import logging
import time

from os import listdir, remove
from os.path import isfile, join
from threading import Thread

# Constants
FOLDER_PATH_MAC = "/Users/ast/Desktop/test_data"
FOLDER_PATH_PI_OLD = "/home/pi/test_data"
FOLDER_PATH_CCTV = "/home/pi/cctv_data"
FOLDER_PATH_DEV = "/home/pi/cctv_test2"
FOLDER_PATH = FOLDER_PATH_DEV
TESTING_DEFAULT_BEFORE_DAYS = 15

class FileProcessor(object):

	def __init__(self):
		self.redis = qm.ConnectToRedis()
		self.DECAY_FLAG = False
		self.gd = GoogleDrive(self.redis)

	def start(self):
		# start all threads here
		t1 = Thread(target=self.process_jobs, args=())
		t1.daemon = True
		t1.start()

		t2 = Thread(target=self.process_uploaded_files, args=())
		t2.daemon = True
		t2.start()

		t3 = Thread(target=self.find_decayed_files, args=())
		t3.daemon = True
		t3.start()

		return self

	def process_jobs(self):		
		while True:
			logging.debug("ENTRY - processJobs")

			# Check if jobs are present in the queue
			if (qm.get_unprocessed_queue_size(self.redis) > 0):
				# get a job from top of the queue
				currentFileName = qm.print_unprocessed_queue(self.redis, 0, 0)[0].decode('ascii')
				logging.debug(currentFileName)

				# get file path
				currentFilePath = self.generate_file_path(currentFileName)
				logging.debug(currentFilePath)

				# add file to transient processing holder
				qm.transient_processing(self.redis, currentFileName)

				# check if file exists
				if(self.check_if_file_exists(currentFilePath)):
					# ask google drive to upload file
					if (self.gd.upload_file(currentFileName, currentFilePath)):
						logging.debug("File successfully uploaded : " + currentFileName)

						# remove element from unprocessed queue
						if (qm.pop_element_from_unprocessed_queue(self.redis) == currentFileName):
							# add element to uploaded queue
							qm.add_to_uploaded_queue(self.redis, currentFileName)
							logging.debug("Done processing file : " + currentFileName)
						else:
							# queue is corrupted
							logging.error("Queue corrupted. Needs to be looked into")
							logging.error("QUEUE DUMP")
							qm.printUnprocessedQueue(self.redis, 0, -1)
					else:
						logging.error("Error uploading file : " + currentFileName)
				else:
					qm.pop_element_from_unprocessed_queue(self.redis)
					logging.info("Fixed system corruption")
			else:
				self.fix_queue()
				# logging.info("wait for jobs to be added to unprocessed queue")
				time.sleep(10)

			logging.debug("EXIT - processJobs")

	def process_uploaded_files(self):
		while True:
			logging.debug("ENTRY - processUploadedFiles")

			# Check if files are present to be deleted
			if (qm.get_uploaded_queue_size(self.redis) > 0):

				# get a job from top of the queue
				currentFileName = qm.print_uploaded_queue(self.redis, 0, 0)[0].decode('ascii')

				# get file path
				currentFilePath = self.generate_file_path(currentFileName)
				logging.debug(currentFilePath)

				# add file to transient processing holder
				qm.transient_deleting(self.redis, currentFileName)

				# check if file exists
				if(self.check_if_file_exists(currentFilePath)):
					# delete from File System
					if (self.delete_file_locally(currentFilePath)):
						logging.debug("File deleted from fs : " + currentFileName)

						if (qm.pop_element_from_uploaded_queue(self.redis) == currentFileName):
							logging.debug("Successfully remove element from delete queue")

						else:
							logging.error("Error removing element from delete queue")

					else:
						logging.error("Failed to delete file : " + currentFileName)
				else:
					qm.pop_element_from_uploaded_queue(self.redis)
					logging.info("Fixed queue corruption")
			else:
				logging.debug("wait for jobs to be added to uploaded queue")
				time.sleep(10)

			logging.debug("EXIT - processUploadedFiles")

	def find_decayed_files(self):
		while True:
			logging.debug("ENTRY - processDecay")

			if (self.DECAY_FLAG):
				logging.debug("ENTRY - Find decay")
				self.gd.find_decay(self.redis)
				self.DECAY_FLAG = False
				logging.debug("EXIT - Find decay")

				# check if files are present which need to be deleted
				if (qm.get_deleted_queue_size(self.redis)):

					# pop a job from top of the queue
					fileId = qm.pop_element_from_deleted_queue(self.redis)

					# ask google to delete file
					if (self.gd.delete_file(fileId)):
						# logging.info("File successfully deleted : "+fileId)
						logging.debug("File successfully deleted")
				else:
					# No need to handle this case, as the queue would be regenerated every 24hrs either ways
					logging.error("Unable to delete file")
			else:
				logging.debug("No jobs to be processed. Sleeping for next 24 hours")
				self.DECAY_FLAG = True
				time.sleep(60*60*24)
				# time.sleep(10)

			logging.debug("EXIT - processDecay")

	def generate_file_path(self, fileName):
	    return FOLDER_PATH + "/" + fileName

	def delete_file_locally(self, filePath):
	    # logging.info("FilePath = " + filePath)
	    try:
	        remove(filePath)
	        return True
	    except OSError:
	        return False

	def check_if_file_exists(self, filePath):
		try:
			return isfile(filePath)
		except Exception as err:
			return False

	def fix_queue(self):
		try:
			for file in listdir(FOLDER_PATH):
			    if file.endswith(".avi"):
			        # print(join(FOLDER_PATH+"/", file))
			        qm.add_to_unprocessed_queue(self.redis, file)
		except Exception as err:
			logging.error(err)
