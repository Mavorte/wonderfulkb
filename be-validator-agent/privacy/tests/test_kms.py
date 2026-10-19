"""KmsKeyProvider proti moto (mock KMS). Živý KMS se netestuje."""
import boto3
import pytest
from moto import mock_aws

from signature_privacy import DecryptionError, KmsKeyProvider, decrypt_image, encrypt_image


@pytest.fixture(scope="module")
def kms():
    with mock_aws():
        client = boto3.client("kms", region_name="eu-central-1")
        key_id = client.create_key(Description="test")["KeyMetadata"]["KeyId"]
        client.create_alias(AliasName="alias/wonderfulkb-signatures", TargetKeyId=key_id)
        yield client


def test_round_trip_via_alias(kms, sig_png, ctx):
    p = KmsKeyProvider(client=kms)                       # výchozí alias
    blob = encrypt_image(sig_png, ctx, p)
    assert decrypt_image(blob, ctx, p) == sig_png
    assert sig_png not in blob


def test_wrong_context_fails(kms, sig_png, ctx):
    p = KmsKeyProvider(client=kms)
    blob = encrypt_image(sig_png, ctx, p)
    with pytest.raises(DecryptionError):
        decrypt_image(blob, ctx._replace(document_id="doc-2"), p)


class SpyKms:
    """Obálka klienta, která si pamatuje parametry volání."""

    def __init__(self, client):
        self._c, self.calls = client, []
        self.exceptions = client.exceptions

    def __getattr__(self, name):
        fn = getattr(self._c, name)

        def call(**kw):
            self.calls.append((name, kw))
            return fn(**kw)
        return call


def test_kms_gets_encryption_context_and_aes256(kms, ctx):
    spy = SpyKms(kms)
    KmsKeyProvider(client=spy).generate_data_key(ctx)
    name, kw = spy.calls[0]
    assert name == "generate_data_key" and kw["KeySpec"] == "AES_256"
    assert kw["EncryptionContext"] == {"case_id": "case-1", "document_id": "doc-1", "signature_id": "sig_01"}


def test_other_key_cannot_decrypt(kms, sig_png, ctx):
    other = kms.create_key()["KeyMetadata"]["KeyId"]
    blob = encrypt_image(sig_png, ctx, KmsKeyProvider(client=kms))
    with pytest.raises(DecryptionError):
        decrypt_image(blob, ctx, KmsKeyProvider(other, client=kms))


def test_corrupted_wrapped_key_fails(kms, sig_png, ctx):
    p = KmsKeyProvider(client=kms)
    blob = bytearray(encrypt_image(sig_png, ctx, p))
    blob[20] ^= 0xFF
    with pytest.raises(DecryptionError):
        decrypt_image(bytes(blob), ctx, p)
