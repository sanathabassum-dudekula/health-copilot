from app import storage


def test_storage_uses_loaded_settings_for_client_and_bucket(monkeypatch, tmp_path):
    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setattr(storage.settings, "AWS_ENDPOINT_URL_S3", "https://s3.example.test")
    monkeypatch.setattr(storage.settings, "AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setattr(storage.settings, "AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(storage.settings, "AWS_REGION", "test-region")
    monkeypatch.setattr(storage.settings, "S3_BUCKET_NAME", "test-bucket")

    client_options = {}

    class FakeS3:
        def put_object(self, **kwargs):
            self.put = kwargs

        def download_file(self, *args):
            self.download = args

        def delete_object(self, **kwargs):
            self.delete = kwargs

    fake_client = FakeS3()

    def fake_client_factory(service, **kwargs):
        client_options.update(service=service, **kwargs)
        return fake_client

    monkeypatch.setattr(storage.boto3, "client", fake_client_factory)

    assert storage.get_s3_client() is fake_client
    assert client_options["service"] == "s3"
    assert client_options["endpoint_url"] == "https://s3.example.test"
    assert client_options["aws_access_key_id"] == "test-access"
    assert client_options["aws_secret_access_key"] == "test-secret"
    assert client_options["region_name"] == "test-region"

    storage.upload_file("uploads/test.pdf", b"contents", "application/pdf")
    destination = str(tmp_path / "download.pdf")
    storage.download_file("uploads/test.pdf", destination)
    storage.delete_file("uploads/test.pdf")

    assert fake_client.put["Bucket"] == "test-bucket"
    assert fake_client.download == ("test-bucket", "uploads/test.pdf", destination)
    assert fake_client.delete == {
        "Bucket": "test-bucket",
        "Key": "uploads/test.pdf",
    }
