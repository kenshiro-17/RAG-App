from __future__ import annotations

import os
from abc import ABC, abstractmethod

import boto3

from app.core.config import get_settings


class StorageProvider(ABC):
    @abstractmethod
    def save_bytes(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _full_path(self, key: str) -> str:
        path = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def save_bytes(self, key: str, data: bytes) -> str:
        path = self._full_path(key)
        with open(path, "wb") as f:
            f.write(data)
        return key

    def read_bytes(self, key: str) -> bytes:
        with open(self._full_path(key), "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        path = self._full_path(key)
        if os.path.exists(path):
            os.remove(path)


class S3StorageProvider(StorageProvider):
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def save_bytes(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def read_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_backend.lower() == "s3":
        return S3StorageProvider()
    return LocalStorageProvider(settings.local_storage_path)
