import pytest
from wtforms.validators import StopValidation, ValidationError

from atat.forms.validators import *


class TestNumber:
    @pytest.mark.parametrize("valid", ["0", "12", "-12"])
    def test_Number_accepts_integers(self, valid, dummy_form, dummy_field):
        validator = number()
        dummy_field.data = valid
        validator(dummy_form, dummy_field)

    @pytest.mark.parametrize("invalid", ["12.1", "two"])
    def test_Number_rejects_anything_else(self, invalid, dummy_form, dummy_field):
        validator = number()
        dummy_field.data = invalid
        with pytest.raises(ValidationError):
            validator(dummy_form, dummy_field)


class TestPhoneNumber:
    @pytest.mark.parametrize("valid", ["12345", "1234567890", "(123) 456-7890"])
    def test_PhoneNumber_accepts_valid_numbers(self, valid, dummy_form, dummy_field):
        validator = phone_number()
        dummy_field.data = valid
        validator(dummy_form, dummy_field)

    @pytest.mark.parametrize(
        "invalid", ["1234", "123456", "1234567abc", "(123) 456-789012"]
    )
    def test_PhoneNumber_rejects_invalid_numbers(
        self, invalid, dummy_form, dummy_field
    ):
        validator = phone_number()
        dummy_field.data = invalid
        with pytest.raises(ValidationError):
            validator(dummy_form, dummy_field)


class TestName:
    @pytest.mark.parametrize("valid", ["a", "abcde", "hi mark", "cloud9", "niña"])
    def test_Name_accepts_letters(self, valid, dummy_form, dummy_field):
        validator = name()
        dummy_field.data = valid
        validator(dummy_form, dummy_field)

    @pytest.mark.parametrize(
        "invalid",
        ["", "/my name", ":-)", "Name&Name", "Ke$ha", "A^Name", "#yourvalidname"],
    )
    def test_Name_rejects_invalid_characters(self, invalid, dummy_form, dummy_field):
        validator = name()
        dummy_field.data = invalid
        with pytest.raises(ValidationError):
            validator(dummy_form, dummy_field)


class TestListItemsUnique:
    @pytest.mark.parametrize("valid", [["a", "aa", "aaa"], ["one", "two", "three"]])
    def test_ListItemsUnique_allows_unique_items(self, valid, dummy_form, dummy_field):
        validator = list_items_unique()
        dummy_field.data = valid
        validator(dummy_form, dummy_field)

    @pytest.mark.parametrize(
        "invalid", [["a", "a", "a"], ["one", "two", "two", "three"]]
    )
    def test_ListItemsUnique_rejects_duplicate_names(
        self, invalid, dummy_form, dummy_field
    ):
        validator = list_items_unique()
        dummy_field.data = invalid
        with pytest.raises(ValidationError):
            validator(dummy_form, dummy_field)


class TestFileLength:
    def test_FileLength(self, dummy_form, dummy_field, pdf_upload):
        validator = file_length(max_length=1)
        dummy_field.data = pdf_upload

        with pytest.raises(ValidationError):
            validator(dummy_form, dummy_field)

        dummy_field.data = "random string"
        assert validator(dummy_form, dummy_field)


class TestListItemRequired:
    @pytest.mark.parametrize("valid", [[" a", ""], ["a ", ""], ["a", ""]])
    def test_ListItemRequired(self, valid, dummy_form, dummy_field):
        validator = list_item_required()
        dummy_field.data = valid
        validator(dummy_form, dummy_field)

    @pytest.mark.parametrize("invalid", [[""], ["    "], [None], []])
    def test_ListItemRequired_rejects_blank_names(
        self, invalid, dummy_form, dummy_field
    ):
        validator = list_item_required()
        dummy_field.data = invalid
        with pytest.raises(ValidationError):
            validator(dummy_form, dummy_field)
