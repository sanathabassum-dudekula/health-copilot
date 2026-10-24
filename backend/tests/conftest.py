import os
import tempfile

_tmp = tempfile.mkdtemp()  # tests never touch Postgres; file DB so background-task threads share it
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["AWS_ENDPOINT_URL_S3"] = ""
os.environ["AWS_ACCESS_KEY_ID"] = ""
os.environ["AWS_SECRET_ACCESS_KEY"] = ""
