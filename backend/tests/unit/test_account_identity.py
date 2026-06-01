"""Unit tests for Phase 2 — identifier normalization + keyed HMAC.

Golden vectors are computed from first principles so the test itself acts as
the spec-compliance record.  If a vector changes unexpectedly the test fails
loudly, preventing silent regression.
"""

from __future__ import annotations

from manifold.domain.account_identity import (
    CURRENCY_SENTINEL,
    MULTI_CURRENCY_PROVIDERS,
    extract_identifiers,
    normalize_currency,
    normalize_iban,
    normalize_scan,
)
from manifold.providers.types import AccountData
from manifold.security.fingerprint import compute_identifier_hmac

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

SECRET = "test-secret-key"


def _make_account(**kwargs) -> AccountData:
    defaults = dict(
        provider_account_id="acct-001",
        account_type="TRANSACTION",
        currency="GBP",
        display_name="Test Account",
        iban=None,
        sort_code=None,
        account_number=None,
    )
    defaults.update(kwargs)
    return AccountData(**defaults)


# ---------------------------------------------------------------------------
# normalize_iban
# ---------------------------------------------------------------------------


class TestNormalizeIban:
    def test_valid_iban_canonical(self):
        # GB29NWBK60161331926819 is a well-known example from the ISO 7064 spec.
        assert normalize_iban("GB29NWBK60161331926819") == "GB29NWBK60161331926819"

    def test_valid_iban_lowercase_normalized(self):
        assert normalize_iban("gb29nwbk60161331926819") == "GB29NWBK60161331926819"

    def test_valid_iban_with_spaces_stripped(self):
        # IBANs are often printed with spaces every 4 chars.
        assert normalize_iban("GB29 NWBK 6016 1331 9268 19") == "GB29NWBK60161331926819"

    def test_valid_iban_with_dashes_stripped(self):
        assert normalize_iban("GB29-NWBK-6016-1331-9268-19") == "GB29NWBK60161331926819"

    def test_invalid_iban_wrong_checksum_rejected(self):
        # Flip one digit to break the mod-97 check.
        assert normalize_iban("GB00NWBK60161331926819") is None

    def test_none_returns_none(self):
        assert normalize_iban(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_iban("") is None

    def test_too_short_returns_none(self):
        assert normalize_iban("GB29") is None

    def test_non_iban_garbage_rejected(self):
        assert normalize_iban("NOT-AN-IBAN") is None

    def test_german_iban_valid(self):
        # DE89370400440532013000 — another well-known ISO example.
        assert normalize_iban("DE89370400440532013000") == "DE89370400440532013000"

    def test_german_iban_with_spaces(self):
        assert normalize_iban("DE89 3704 0044 0532 0130 00") == "DE89370400440532013000"

    def test_mod97_boundary_exactly_1_passes(self):
        # Any valid IBAN must satisfy int(rearranged_numeric) % 97 == 1.
        result = normalize_iban("GB29NWBK60161331926819")
        assert result is not None

    def test_mod97_boundary_not_1_fails(self):
        # Increment last digit by 1 to break checksum.
        assert normalize_iban("GB29NWBK60161331926820") is None


# ---------------------------------------------------------------------------
# normalize_scan
# ---------------------------------------------------------------------------


class TestNormalizeScan:
    def test_clean_sort_code_and_number(self):
        assert normalize_scan("123456", "12345678") == "123456:12345678"

    def test_sort_code_with_dashes_stripped(self):
        assert normalize_scan("12-34-56", "12345678") == "123456:12345678"

    def test_sort_code_with_spaces_stripped(self):
        assert normalize_scan("12 34 56", "12345678") == "123456:12345678"

    def test_account_number_zero_padded_to_8(self):
        # Short number (e.g. 6-digit) must be left-padded with zeros.
        assert normalize_scan("123456", "123456") == "123456:00123456"

    def test_account_number_already_8_digits_unchanged(self):
        assert normalize_scan("601613", "31926819") == "601613:31926819"

    def test_sort_code_none_returns_none(self):
        assert normalize_scan(None, "12345678") is None

    def test_account_number_none_returns_none(self):
        assert normalize_scan("123456", None) is None

    def test_both_none_returns_none(self):
        assert normalize_scan(None, None) is None

    def test_sort_code_wrong_length_returns_none(self):
        # 5 digits — invalid sort code.
        assert normalize_scan("12345", "12345678") is None

    def test_sort_code_7_digits_returns_none(self):
        assert normalize_scan("1234567", "12345678") is None

    def test_empty_sort_code_returns_none(self):
        assert normalize_scan("", "12345678") is None

    def test_empty_account_number_returns_none(self):
        assert normalize_scan("123456", "") is None

    def test_real_truelayer_fixture_values(self):
        # Values from tests/fixtures/truelayer_responses/accounts.json
        assert normalize_scan("601613", "31926819") == "601613:31926819"


# ---------------------------------------------------------------------------
# normalize_aba
# ---------------------------------------------------------------------------


class TestNormalizeAba:
    def test_clean_routing_and_number(self):
        from manifold.domain.account_identity import normalize_aba

        assert normalize_aba("021000021", "123456789") == "021000021:123456789"

    def test_routing_with_dashes_stripped(self):
        from manifold.domain.account_identity import normalize_aba

        assert normalize_aba("021-000-021", "123456789") == "021000021:123456789"

    def test_routing_none_returns_none(self):
        from manifold.domain.account_identity import normalize_aba

        assert normalize_aba(None, "123456789") is None

    def test_account_number_none_returns_none(self):
        from manifold.domain.account_identity import normalize_aba

        assert normalize_aba("021000021", None) is None

    def test_both_empty_returns_none(self):
        from manifold.domain.account_identity import normalize_aba

        assert normalize_aba("", "") is None


# ---------------------------------------------------------------------------
# normalize_currency
# ---------------------------------------------------------------------------


class TestNormalizeCurrency:
    def test_uppercase_passthrough(self):
        assert normalize_currency("GBP") == "GBP"

    def test_lowercase_uppercased(self):
        assert normalize_currency("gbp") == "GBP"

    def test_whitespace_trimmed(self):
        assert normalize_currency("  USD  ") == "USD"

    def test_none_returns_sentinel(self):
        assert normalize_currency(None) == CURRENCY_SENTINEL

    def test_empty_returns_sentinel(self):
        assert normalize_currency("") == CURRENCY_SENTINEL

    def test_whitespace_only_returns_sentinel(self):
        assert normalize_currency("   ") == CURRENCY_SENTINEL

    def test_sentinel_value_is_dash(self):
        assert CURRENCY_SENTINEL == "-"


# ---------------------------------------------------------------------------
# compute_identifier_hmac
# ---------------------------------------------------------------------------


class TestComputeIdentifierHmac:
    def test_output_is_64_char_hex(self):
        result = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", SECRET)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic_same_inputs(self):
        h1 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", SECRET)
        h2 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", SECRET)
        assert h1 == h2

    def test_different_user_id_changes_digest(self):
        h1 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", SECRET)
        h2 = compute_identifier_hmac("user-2", "iban", "GB29NWBK60161331926819", SECRET)
        assert h1 != h2

    def test_different_id_type_changes_digest(self):
        # SCAN and IBAN with the same value string must never collide.
        h1 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", SECRET)
        h2 = compute_identifier_hmac("user-1", "scan", "GB29NWBK60161331926819", SECRET)
        assert h1 != h2

    def test_different_value_changes_digest(self):
        h1 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", SECRET)
        h2 = compute_identifier_hmac("user-1", "iban", "DE89370400440532013000", SECRET)
        assert h1 != h2

    def test_different_secret_changes_digest(self):
        h1 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", "secret-a")
        h2 = compute_identifier_hmac("user-1", "iban", "GB29NWBK60161331926819", "secret-b")
        assert h1 != h2

    def test_golden_vector(self):
        """Golden vector — computed independently to lock the algorithm.

        If this test fails, the HMAC construction changed and all stored
        ``value_hmac`` rows in the DB would be invalidated.  Only update this
        vector deliberately and with a matching DB migration to rehash.
        """
        import hmac as stdlib_hmac

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        # Reproduce the derivation chain independently.
        secret = "golden-secret"
        secret_bytes = secret.encode("utf-8")
        info = b"manifold-fingerprint"
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(secret_bytes)
        preimage = b"user-golden:iban:GB29NWBK60161331926819"
        expected = stdlib_hmac.new(key, preimage, "sha256").hexdigest()

        result = compute_identifier_hmac("user-golden", "iban", "GB29NWBK60161331926819", secret)
        assert result == expected
        # Sanity: it really is 64 hex chars.
        assert len(result) == 64


# ---------------------------------------------------------------------------
# extract_identifiers
# ---------------------------------------------------------------------------


class TestExtractIdentifiers:
    def test_iban_only_account(self):
        account = _make_account(iban="GB29NWBK60161331926819")
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert len(rows) == 1
        id_type, value_hmac, currency = rows[0]
        assert id_type == "iban"
        assert len(value_hmac) == 64
        assert currency == CURRENCY_SENTINEL

    def test_scan_only_account(self):
        account = _make_account(sort_code="601613", account_number="31926819")
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert len(rows) == 1
        id_type, _, currency = rows[0]
        assert id_type == "scan"
        assert currency == CURRENCY_SENTINEL

    def test_iban_and_scan_both_emitted(self):
        account = _make_account(
            iban="GB29NWBK60161331926819",
            sort_code="601613",
            account_number="31926819",
        )
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        types = {r[0] for r in rows}
        assert types == {"iban", "scan"}

    def test_invalid_iban_skipped(self):
        # Bad checksum → iban identifier must NOT be emitted.
        account = _make_account(iban="GB00NWBK60161331926819")
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert not any(r[0] == "iban" for r in rows)

    def test_scan_missing_sort_code_skipped(self):
        account = _make_account(account_number="31926819")
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert not any(r[0] == "scan" for r in rows)

    def test_scan_missing_account_number_skipped(self):
        account = _make_account(sort_code="601613")
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert not any(r[0] == "scan" for r in rows)

    def test_no_identifier_account_returns_empty_list(self):
        # Wise-no-details: account_number only, no sort_code, no IBAN.
        account = _make_account(account_number="12345678")
        rows = extract_identifiers(account, "user-1", "wise", SECRET)
        assert rows == []

    def test_completely_bare_account_returns_empty_list(self):
        account = _make_account()
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert rows == []

    def test_single_currency_provider_uses_sentinel(self):
        account = _make_account(iban="GB29NWBK60161331926819", currency="GBP")
        rows = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert all(r[2] == CURRENCY_SENTINEL for r in rows)

    def test_multi_currency_provider_uses_real_currency(self, monkeypatch):
        # Temporarily add "wise" to MULTI_CURRENCY_PROVIDERS to exercise the branch.
        import manifold.domain.account_identity as mod

        monkeypatch.setattr(mod, "MULTI_CURRENCY_PROVIDERS", frozenset({"wise"}))
        account = _make_account(iban="GB29NWBK60161331926819", currency="USD")
        rows = extract_identifiers(account, "user-1", "wise", SECRET)
        assert rows[0][2] == "USD"

    def test_hmac_is_deterministic_across_calls(self):
        account = _make_account(iban="GB29NWBK60161331926819")
        rows1 = extract_identifiers(account, "user-1", "truelayer", SECRET)
        rows2 = extract_identifiers(account, "user-1", "truelayer", SECRET)
        assert rows1 == rows2

    def test_different_user_id_yields_different_hmac(self):
        account = _make_account(iban="GB29NWBK60161331926819")
        rows1 = extract_identifiers(account, "user-1", "truelayer", SECRET)
        rows2 = extract_identifiers(account, "user-2", "truelayer", SECRET)
        # Same id_type and currency, different hmac.
        assert rows1[0][1] != rows2[0][1]

    def test_scan_account_number_zero_padded(self):
        # Account number shorter than 8 digits must be zero-padded before hashing.
        account_short = _make_account(sort_code="601613", account_number="123456")
        account_padded = _make_account(sort_code="601613", account_number="00123456")
        rows_short = extract_identifiers(account_short, "user-1", "truelayer", SECRET)
        rows_padded = extract_identifiers(account_padded, "user-1", "truelayer", SECRET)
        # Both normalizations should produce the same HMAC.
        assert rows_short[0][1] == rows_padded[0][1]

    def test_iban_with_spaces_same_hmac_as_clean(self):
        account_spaced = _make_account(iban="GB29 NWBK 6016 1331 9268 19")
        account_clean = _make_account(iban="GB29NWBK60161331926819")
        rows_spaced = extract_identifiers(account_spaced, "user-1", "truelayer", SECRET)
        rows_clean = extract_identifiers(account_clean, "user-1", "truelayer", SECRET)
        assert rows_spaced[0][1] == rows_clean[0][1]

    def test_iban_lowercase_same_hmac_as_uppercase(self):
        account_lower = _make_account(iban="gb29nwbk60161331926819")
        account_upper = _make_account(iban="GB29NWBK60161331926819")
        rows_lower = extract_identifiers(account_lower, "user-1", "truelayer", SECRET)
        rows_upper = extract_identifiers(account_upper, "user-1", "truelayer", SECRET)
        assert rows_lower[0][1] == rows_upper[0][1]

    def test_multi_currency_providers_set_is_empty_by_default(self):
        # §6 gate: MULTI_CURRENCY_PROVIDERS must be empty until a multi-currency
        # adapter ships.  Fail loudly if someone accidentally pre-populates it.
        assert MULTI_CURRENCY_PROVIDERS == frozenset()
