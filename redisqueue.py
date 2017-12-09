import redis

# Redis
PI_IP = "192.168.0.107"
LOCALHOST_IP = "127.0.0.1"
IP = LOCALHOST_IP
PORT = 6379


# Redis functions
def GetRedisConnectionPool(hostname=IP, port=PORT):
    return redis.ConnectionPool(host=hostname, port=port, db=0)


def ConnectToRedis(pool=GetRedisConnectionPool()):
    return redis.Redis(connection_pool=pool)


# Permenat Queues
UNPROCESSED = "UNPROCESSED"
UPLOADED = "UPLOADED"
DELETED = "DRIVE_DELETE"

# Transient states
ELEMENT_PROCESSING = "EP"
ELEMENT_UPLOADING = "EU"
ELEMENT_DELETING = "ED"


# Operations to add to queue
def add_to_unprocessed_queue(redis, element):
    redis.rpush(UNPROCESSED, element);


def add_to_uploaded_queue(redis, element):
    redis.rpush(UPLOADED, element)


def add_to_deleted_queue(redis, element):
    redis.rpush(DELETED, element)


# Operations to delete from queue
# def deleteFromUnprocessedQueue(redis, element):
#     redis.lrem(UNPROCESSED, element)


# def deleteFromUploadedQueue(redis, element):
#     redis.lrem(UPLOADED, element)


# ----------- Operations to remove a single element from the queue
def pop_element_from_unprocessed_queue(redis):
    return redis.lpop(UNPROCESSED).decode('ascii')


def pop_element_from_uploaded_queue(redis):
    return redis.lpop(UPLOADED).decode('ascii')


def pop_element_from_deleted_queue(redis):
    return redis.lpop(DELETED).decode('ascii')


# ----------- Operations to transfer to intermediate queue states for fail safe operations
def transient_processing(redis, element):
    return redis.set(ELEMENT_PROCESSING, element)


# def transientUploading(redis, element):
#     return redis.set(ELEMENT_UPLOADING, element)

def transient_deleting(redis, element):
    return redis.set(ELEMENT_DELETING, element)


# ----------- General queue functions
def print_unprocessed_queue(redis, start, end):
    return redis.lrange(UNPROCESSED, start, end)


def print_uploaded_queue(redis, start, end):
    return redis.lrange(UPLOADED, start, end)


# def printDeletedQueue(redis, start, end):
#     return redis.lrange(DELETED, start, end)


def get_unprocessed_queue_size(redis):
    return redis.llen(UNPROCESSED)


def get_uploaded_queue_size(redis):
    return redis.llen(UPLOADED)


def get_deleted_queue_size(redis):
    return redis.llen(DELETED)

