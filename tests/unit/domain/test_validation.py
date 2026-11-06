"""Юнит-тесты функций проверки и разбора ввода: акцент на граничных значениях."""

from __future__ import annotations

from datetime import date

import pytest

from src.domain.enums import FileType, Role, SortField, SortOrder
from src.domain.exceptions import (
    EmptyFieldError,
    FieldTooLongError,
    InvalidDateError,
    InvalidEmailError,
    InvalidLoginError,
    InvalidYesNoError,
    LoginRequiredError,
    NotPositiveIntegerError,
    PasswordRequiredError,
    PasswordTooShortError,
    PasswordTooWeakError,
    UnknownFileTypeError,
    UnknownRoleError,
    UnknownSortOptionError,
)
from src.domain.validation import (
    MAX_NAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    PASSWORD_REQUIREMENTS,
    SORT_OPTIONS,
    OptionalParser,
    parse_date,
    parse_file_type,
    parse_positive_int,
    parse_role,
    parse_sort_option,
    parse_yes_no,
    require_text,
    role_hint,
    validate_credentials_present,
    validate_email,
    validate_login,
    validate_password,
)


class TestValidateLogin:
    @pytest.mark.parametrize(
        "login",
        ["abc", "a" * 32, "user_1", "user-1", "USER", "a1b", "___", "---", "123"],
    )
    def test_accepts_valid_login(self, login):
        validate_login(login)

    @pytest.mark.parametrize(
        "login",
        [
            "",
            "ab",
            "a" * 33,
            "user name",
            "user!",
            "юзер",
            "user@x",
            " abc",
            "abc ",
            "ab\n",
            "abc\n",
            "abc\r\n",
            "a.b",
        ],
    )
    def test_rejects_invalid_login(self, login):
        with pytest.raises(InvalidLoginError):
            validate_login(login)

    def test_length_boundaries(self):
        validate_login("a" * 3)
        validate_login("a" * 32)
        with pytest.raises(InvalidLoginError):
            validate_login("a" * 2)
        with pytest.raises(InvalidLoginError):
            validate_login("a" * 33)


class TestValidateEmail:
    @pytest.mark.parametrize(
        "email", ["a@b.c", "user@example.org", "a.b+c@sub.domain.ru", "я@б.рф"]
    )
    def test_accepts_valid_email(self, email):
        validate_email(email)

    @pytest.mark.parametrize(
        "email",
        ["", "a@b.c\n", "a@b", "@b.c", "a@.c", "a@b.", "a b@c.d", "a@@b.c", "a@b c.d", "a@b.c d"],
    )
    def test_rejects_invalid_email(self, email):
        with pytest.raises(InvalidEmailError):
            validate_email(email)


class TestValidatePassword:
    def test_minimum_length_is_eight(self):
        assert MIN_PASSWORD_LENGTH == 8

    def test_accepts_exactly_minimum_with_all_character_kinds(self):
        password = "Abcdef1!"
        assert len(password) == MIN_PASSWORD_LENGTH
        validate_password(password)

    def test_rejects_one_below_minimum_even_if_complex(self):
        password = "Abcde1!"
        assert len(password) == MIN_PASSWORD_LENGTH - 1
        with pytest.raises(PasswordTooShortError):
            validate_password(password)

    def test_rejects_empty(self):
        with pytest.raises(PasswordTooShortError):
            validate_password("")

    def test_accepts_very_long(self):
        validate_password("A1!" + "a" * 10_000)

    @pytest.mark.parametrize(
        "password",
        ["Password1!", "Пароль1!А", "A1!aaaaa", "ПаРоЛь-9й", "1!AAAAAA", "!1aAaaaa", "a1A_bbbb"],
    )
    def test_accepts_strong_passwords(self, password):
        validate_password(password)

    @pytest.mark.parametrize(
        ("password", "missing"),
        [
            ("password1!", ["заглавную букву"]),
            ("PASSWORD1!", []),
            ("Password!!", ["цифру"]),
            ("Password11", ["специальный символ"]),
            ("password!!", ["заглавную букву", "цифру"]),
            ("password11", ["заглавную букву", "специальный символ"]),
            ("Passwordd", ["цифру", "специальный символ"]),
            ("passworddd", ["заглавную букву", "цифру", "специальный символ"]),
        ],
    )
    def test_reports_exactly_what_is_missing(self, password, missing):
        if not missing:
            validate_password(password)
            return
        with pytest.raises(PasswordTooWeakError) as error:
            validate_password(password)
        assert error.value.details["missing"] == ", ".join(missing)

    @pytest.mark.parametrize("password", ["12345678", "        ", "\t\t\t\t\t\t\t\t", "aaaaaaaa"])
    def test_rejects_passwords_without_complexity(self, password):
        with pytest.raises(PasswordTooWeakError):
            validate_password(password)

    def test_spaces_are_not_special_characters(self):
        with pytest.raises(PasswordTooWeakError, match="специальный символ"):
            validate_password("Pass word1")

    def test_decimal_digit_of_other_scripts_counts_as_digit(self):
        validate_password("Abcdef٣!")

    def test_lowercase_cyrillic_is_not_uppercase(self):
        with pytest.raises(PasswordTooWeakError, match="заглавную букву"):
            validate_password("пароль1!х")

    def test_underscore_and_hyphen_count_as_special(self):
        validate_password("Abcdef1_")
        validate_password("Abcdef1-")

    def test_length_is_checked_before_complexity(self):
        with pytest.raises(PasswordTooShortError):
            validate_password("abc")

    def test_error_mentions_minimum_for_short_password(self):
        with pytest.raises(PasswordTooShortError, match=str(MIN_PASSWORD_LENGTH)):
            validate_password("x")

    def test_requirements_hint_mentions_every_rule(self):
        assert str(MIN_PASSWORD_LENGTH) in PASSWORD_REQUIREMENTS
        for word in ("заглавной", "цифрой", "символом"):
            assert word in PASSWORD_REQUIREMENTS


class TestValidateCredentialsPresent:
    def test_accepts_valid_pair(self):
        validate_credentials_present("admin", "x")

    def test_password_length_not_checked_on_login(self):
        validate_credentials_present("admin", "1")

    @pytest.mark.parametrize("login", ["", "   ", "\t\n"])
    def test_blank_login(self, login):
        with pytest.raises(LoginRequiredError):
            validate_credentials_present(login, "pw")

    def test_blank_password(self):
        with pytest.raises(PasswordRequiredError):
            validate_credentials_present("admin", "")

    def test_whitespace_only_password_is_allowed(self):
        validate_credentials_present("admin", "   ")

    def test_login_is_stripped_before_format_check(self):
        validate_credentials_present("  admin  ", "pw")

    def test_invalid_login_format(self):
        with pytest.raises(InvalidLoginError):
            validate_credentials_present("a!", "pw")


class TestRequireText:
    def test_strips_edges(self):
        assert require_text("  текст  ", "Поле") == "текст"

    def test_keeps_inner_spaces(self):
        assert require_text("a  b", "Поле") == "a  b"

    @pytest.mark.parametrize("raw", ["", " ", "\t", "\n  \n"])
    def test_blank_is_rejected(self, raw):
        with pytest.raises(EmptyFieldError):
            require_text(raw, "Поле")

    def test_exactly_max_length_is_allowed(self):
        assert len(require_text("a" * MAX_NAME_LENGTH, "Поле")) == MAX_NAME_LENGTH

    def test_one_over_max_length_is_rejected(self):
        with pytest.raises(FieldTooLongError):
            require_text("a" * (MAX_NAME_LENGTH + 1), "Поле")

    def test_length_is_measured_after_strip(self):
        require_text(" " + "a" * MAX_NAME_LENGTH + " ", "Поле")

    def test_custom_limit(self):
        assert require_text("abc", "Поле", 3) == "abc"
        with pytest.raises(FieldTooLongError):
            require_text("abcd", "Поле", 3)

    def test_error_names_field(self):
        with pytest.raises(EmptyFieldError, match="Название"):
            require_text("", "Название")


class TestParsePositiveInt:
    @pytest.mark.parametrize(
        ("raw", "expected"), [("1", 1), (" 5 ", 5), ("007", 7), ("999999", 999999)]
    )
    def test_valid(self, raw, expected):
        assert parse_positive_int(raw) == expected

    @pytest.mark.parametrize(
        "raw", ["0", "00", "-1", "+1", "1.5", "1,5", "", " ", "abc", "1a", "1 2", "١٢x"]
    )
    def test_invalid(self, raw):
        with pytest.raises(NotPositiveIntegerError):
            parse_positive_int(raw)

    def test_zero_is_the_lower_boundary(self):
        with pytest.raises(NotPositiveIntegerError):
            parse_positive_int("0")
        assert parse_positive_int("1") == 1


class TestParseYesNo:
    @pytest.mark.parametrize("raw", ["y", "Y", "yes", "YES", "д", "Да", " да "])
    def test_yes(self, raw):
        assert parse_yes_no(raw) is True

    @pytest.mark.parametrize("raw", ["n", "N", "no", "н", "Нет", " нет "])
    def test_no(self, raw):
        assert parse_yes_no(raw) is False

    @pytest.mark.parametrize("raw", ["", "maybe", "yy", "1", "0", "дa"])
    def test_invalid(self, raw):
        with pytest.raises(InvalidYesNoError):
            parse_yes_no(raw)


class TestParseRole:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("s", Role.STUDENT),
            ("t", Role.TEACHER),
            ("a", Role.ADMIN),
            ("student", Role.STUDENT),
            ("TEACHER", Role.TEACHER),
            (" Admin ", Role.ADMIN),
            ("S", Role.STUDENT),
        ],
    )
    def test_valid(self, raw, expected):
        assert parse_role(raw) is expected

    @pytest.mark.parametrize("raw", ["", "x", "studen", "students", "ad min", "0"])
    def test_invalid(self, raw):
        with pytest.raises(UnknownRoleError):
            parse_role(raw)

    def test_hint_lists_all_roles(self):
        hint = role_hint()
        for role in Role:
            assert role.value in hint


class TestParseFileType:
    @pytest.mark.parametrize("raw", ["pdf", ".pdf", "PDF", " .Pdf "])
    def test_variants_of_pdf(self, raw):
        assert parse_file_type(raw) is FileType.PDF

    @pytest.mark.parametrize("file_type", list(FileType))
    def test_every_type_is_parsable(self, file_type):
        assert parse_file_type(file_type.value) is file_type

    @pytest.mark.parametrize("raw", ["", "exe", "pdff", "..pdf.", "p df"])
    def test_invalid(self, raw):
        with pytest.raises(UnknownFileTypeError):
            parse_file_type(raw)

    def test_multiple_leading_dots_are_stripped(self):
        assert parse_file_type("..pdf") is FileType.PDF


class TestParseDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("01.01.2000", date(2000, 1, 1)),
            ("2000-01-01", date(2000, 1, 1)),
            ("31.12.2026", date(2026, 12, 31)),
            (" 15.06.2026 ", date(2026, 6, 15)),
            ("29.02.2024", date(2024, 2, 29)),
            ("1.1.2026", date(2026, 1, 1)),
        ],
    )
    def test_valid(self, raw, expected):
        assert parse_date(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "29.02.2023",
            "29.02.1900",
            "30.02.2024",
            "31.04.2026",
            "32.01.2026",
            "00.01.2026",
            "01.13.2026",
            "01.00.2026",
            "2026/01/01",
            "01-01-2026",
            "вчера",
            "2026-13-01",
        ],
    )
    def test_invalid(self, raw):
        with pytest.raises(InvalidDateError):
            parse_date(raw)

    def test_leap_day_of_century_year(self):
        assert parse_date("29.02.2000") == date(2000, 2, 29)


class TestParseSortOption:
    def test_empty_input_means_first_option(self):
        assert parse_sort_option("") == (SortField.UPLOAD_DATE, SortOrder.DESCENDING)
        assert parse_sort_option("   ") == (SortField.UPLOAD_DATE, SortOrder.DESCENDING)

    @pytest.mark.parametrize("number", range(1, len(SORT_OPTIONS) + 1))
    def test_every_option(self, number):
        _label, field, order = SORT_OPTIONS[number - 1]
        assert parse_sort_option(str(number)) == (field, order)

    @pytest.mark.parametrize("raw", ["0", str(len(SORT_OPTIONS) + 1), "-1", "abc", "1.0", "99"])
    def test_out_of_range_or_garbage(self, raw):
        with pytest.raises(UnknownSortOptionError):
            parse_sort_option(raw)

    def test_both_boundaries(self):
        parse_sort_option("1")
        parse_sort_option(str(len(SORT_OPTIONS)))


class TestOptionalParser:
    def test_empty_gives_none(self):
        parser = OptionalParser(parse_positive_int)
        assert parser("") is None
        assert parser("   ") is None

    def test_value_is_delegated(self):
        assert OptionalParser(parse_positive_int)(" 3 ") == 3

    def test_invalid_value_still_raises(self):
        with pytest.raises(NotPositiveIntegerError):
            OptionalParser(parse_positive_int)("0")

    def test_zero_is_not_treated_as_empty(self):
        with pytest.raises(NotPositiveIntegerError):
            OptionalParser(parse_positive_int)("0")
