"""T-06: HostMappingKVS sync (CloudFront KeyValueStore 9host-site-hosts-kvs) via SiteStoragePort.

moto does not implement cloudfront-keyvaluestore, and botocore.Stubber cannot be used without
awscrt (endpoint resolution demands SigV4A), so the client is a small fake whose every request
is validated against the real botocore service model.
"""

import json

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.validate import validate_parameters

import site_storage
from site_storage import (
    S3SiteStorageAdapter,
    delete_host_mapping,
    put_host_mapping,
)

KVS_ARN = "arn:aws:cloudfront::123456789012:key-value-store/0123abcd-0000-0000-0000-000000000000"


_MODEL = boto3.client("cloudfront-keyvaluestore", region_name="us-east-1").meta.service_model


def _validate(op: str, **params) -> None:
    validate_parameters(params, _MODEL.operation_model(op).input_shape)  # raises ParamValidationError


def _client_error(code: str, op: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, op)


class FakeKVS:
    """In-memory cloudfront-keyvaluestore with ETag optimistic concurrency."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.etag_n = 0
        self.calls: list[tuple] = []
        self.fail_next: list[ClientError] = []  # raised by the next put/delete calls, in order
        self.describe_error: Exception | None = None

    @property
    def etag(self) -> str:
        return f"ETAG{self.etag_n}"

    def describe_key_value_store(self, KvsARN):
        _validate("DescribeKeyValueStore", KvsARN=KvsARN)
        self.calls.append(("describe", KvsARN))
        if self.describe_error:
            raise self.describe_error
        return {"KvsARN": KvsARN, "ETag": self.etag, "ItemCount": len(self.store)}

    def _check(self, op, IfMatch):
        if self.fail_next:
            raise self.fail_next.pop(0)
        if IfMatch != self.etag:
            raise _client_error("ConflictException", op)

    def put_key(self, KvsARN, Key, Value, IfMatch):
        _validate("PutKey", KvsARN=KvsARN, Key=Key, Value=Value, IfMatch=IfMatch)
        self.calls.append(("put", Key, Value, IfMatch))
        self._check("PutKey", IfMatch)
        self.store[Key] = Value
        self.etag_n += 1
        return {"ETag": self.etag}

    def delete_key(self, KvsARN, Key, IfMatch):
        _validate("DeleteKey", KvsARN=KvsARN, Key=Key, IfMatch=IfMatch)
        self.calls.append(("delete", Key, IfMatch))
        self._check("DeleteKey", IfMatch)
        if Key not in self.store:
            raise _client_error("ResourceNotFoundException", "DeleteKey")
        del self.store[Key]
        self.etag_n += 1
        return {"ETag": self.etag}


@pytest.fixture
def kvs(monkeypatch):
    fake = FakeKVS()
    monkeypatch.setenv("SITE_HOSTS_KVS_ARN", KVS_ARN)
    monkeypatch.setattr(site_storage, "_get_kvs_client", lambda: fake)
    return fake


# --- put / delete payload shape -------------------------------------------------

def test_put_host_mapping_lowercase_key_and_json_payload(kvs):
    assert put_host_mapping("  Jinks1.Echo9.NET.  ", "echo9", "a1B2c3") is True
    assert kvs.store == {"jinks1.echo9.net": '{"tenant":"echo9","site_id":"a1B2c3"}'}
    assert json.loads(kvs.store["jinks1.echo9.net"]) == {"tenant": "echo9", "site_id": "a1B2c3"}


def test_put_host_mapping_strips_port(kvs):
    put_host_mapping("MyBand.com:443", "acme", "s1")
    assert list(kvs.store) == ["myband.com"]


def test_put_host_mapping_ignores_incomplete_input(kvs):
    assert put_host_mapping("", "acme", "s1") is False
    assert put_host_mapping("x.com", "", "s1") is False
    assert put_host_mapping("x.com", "acme", "") is False
    assert kvs.calls == []


def test_delete_host_mapping_is_idempotent(kvs):
    put_host_mapping("myband.com", "acme", "s1")
    delete_host_mapping("MYBAND.com")
    assert kvs.store == {}
    delete_host_mapping("myband.com")  # already absent -> no raise
    assert kvs.calls[-1][0] == "delete"


# --- ETag flow ------------------------------------------------------------------

def test_etag_from_describe_is_passed_as_if_match(kvs):
    put_host_mapping("a.echo9.net", "acme", "s1")
    put_host_mapping("b.echo9.net", "acme", "s1")
    assert [c[0] for c in kvs.calls] == ["describe", "put", "describe", "put"]
    assert kvs.calls[1][3] == "ETAG0" and kvs.calls[3][3] == "ETAG1"


def test_etag_conflict_retries_once(kvs):
    kvs.fail_next = [_client_error("ConflictException", "PutKey")]
    put_host_mapping("a.echo9.net", "acme", "s1")
    assert kvs.store == {"a.echo9.net": '{"tenant":"acme","site_id":"s1"}'}
    assert [c[0] for c in kvs.calls] == ["describe", "put", "describe", "put"]


def test_repeated_conflict_gives_up_without_raising(kvs, caplog):
    kvs.fail_next = [_client_error("ConflictException", "PutKey")] * 3
    assert put_host_mapping("a.echo9.net", "acme", "s1") is False  # caller can retry later
    assert kvs.store == {}
    assert [c[0] for c in kvs.calls] == ["describe", "put", "describe", "put"]  # exactly one retry
    assert "put_host_mapping failed" in caplog.text


def test_non_conflict_error_not_retried(kvs, caplog):
    kvs.fail_next = [_client_error("AccessDeniedException", "PutKey")]
    assert put_host_mapping("a.echo9.net", "acme", "s1") is False
    assert [c[0] for c in kvs.calls] == ["describe", "put"]
    assert "put_host_mapping failed" in caplog.text


# --- not configured ---------------------------------------------------------------

def test_noop_when_kvs_arn_unset(monkeypatch):
    monkeypatch.delenv("SITE_HOSTS_KVS_ARN", raising=False)

    def boom():
        raise AssertionError("KVS client must not be created when SITE_HOSTS_KVS_ARN is unset")

    monkeypatch.setattr(site_storage, "_get_kvs_client", boom)
    assert put_host_mapping("a.echo9.net", "acme", "s1") is True  # nothing to sync
    assert site_storage.list_host_mappings() == []
    delete_host_mapping("a.echo9.net")
    S3SiteStorageAdapter(None).sync_host_mapping("acme", "s1", ["a.echo9.net"])


def test_fake_rejects_requests_outside_botocore_model():
    with pytest.raises(Exception):
        FakeKVS().put_key(KvsARN=KVS_ARN, Key="k", Value="v")  # IfMatch is required


# --- publish integration ------------------------------------------------------------

def _seed_site(table):
    site_item = {"pk": "TENANT#acme", "sk": "SITE#s1", "name": "Acme", "slug": "acme-band", "template_id": "musician-band"}
    table.put_item(Item=site_item)
    for domain, site_id, status in [
        ("myband.com", "s1", "ACTIVE"),
        ("pending.com", "s1", "PENDING_VALIDATION"),
        ("other.com", "s2", "ACTIVE"),
    ]:
        table.put_item(Item={"pk": "TENANT#acme", "sk": f"DOMAIN#{domain}", "site_id": site_id, "status": status})
    # Another tenant's ACTIVE domain for the same site_id must never be mapped (tenant isolation).
    table.put_item(Item={"pk": "TENANT#evil", "sk": "DOMAIN#evil.com", "site_id": "s1", "status": "ACTIVE"})
    return site_item


def _publish(table, s3):
    import publish_handler

    site_item = _seed_site(table)
    return publish_handler._publish_site(
        table, s3, "acme", "s1", site_item, {"slug": "musician-band"}, "/media/",
        {"updates_blog": True, "events_shows": True, "branding": True},
        storage=S3SiteStorageAdapter(s3),
    )


def test_publish_maps_subdomain_and_active_custom_domains(dynamodb_table, kvs):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="9host-sites")
    result = _publish(dynamodb_table, s3)
    assert result["version"] == 1
    mapping = '{"tenant":"acme","site_id":"s1"}'
    assert kvs.store == {"acme-band.echo9.net": mapping, "myband.com": mapping}


def test_kvs_failure_does_not_break_publish(dynamodb_table, kvs, caplog):
    kvs.describe_error = _client_error("InternalServerException", "DescribeKeyValueStore")
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="9host-sites")
    result = _publish(dynamodb_table, s3)
    assert result["version"] == 1
    assert s3.get_object(Bucket="9host-sites", Key="acme/s1/published/current/index.html")["Body"].read()
    row = dynamodb_table.get_item(Key={"pk": "TENANT#acme", "sk": "SITE#s1"})["Item"]
    assert row["status"] == "published" and int(row["published_version"]) == 1
    assert kvs.store == {}
    assert "put_host_mapping failed" in caplog.text


def test_publish_without_kvs_configured_still_succeeds(dynamodb_table, monkeypatch):
    monkeypatch.delenv("SITE_HOSTS_KVS_ARN", raising=False)
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="9host-sites")
    assert _publish(dynamodb_table, s3)["version"] == 1


def test_publish_records_hostnames_on_in_memory_port(dynamodb_table):
    import publish_handler
    from site_storage import InMemorySiteStorage

    site_item = _seed_site(dynamodb_table)
    storage = InMemorySiteStorage()
    publish_handler._publish_site(
        dynamodb_table, None, "acme", "s1", site_item, {"slug": "musician-band"}, "/media/", {}, storage=storage,
    )
    assert storage.host_mappings == [("acme", "s1", ["acme-band.echo9.net", "myband.com"])]


def test_remove_host_mapping_deletes_keys(kvs):
    storage = S3SiteStorageAdapter(None)
    storage.sync_host_mapping("acme", "s1", ["a.echo9.net", "b.com"])
    storage.remove_host_mapping(["A.echo9.net", "b.com", "never-mapped.com"])
    assert kvs.store == {}
