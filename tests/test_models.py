"""Tests for Gen-UI data models."""

import pytest
from gen_ui.models.field_definitions import (
    FieldInput,
    FormInput,
    FieldAnalysisInput,
)
from gen_ui.models.schema_output import (
    FormFieldSchema,
    GeneratedFormSchema,
)
from gen_ui.models.validation_result import (
    FieldValidationError,
    ValidationResult,
)


class TestFieldInput:
    """Tests for FieldInput model."""

    def test_basic_field(self):
        """Test creating a basic field input."""
        field = FieldInput(name="email")
        assert field.name == "email"
        assert field.required is True
        assert field.hint is None

    def test_field_with_hint(self):
        """Test field with hint."""
        field = FieldInput(
            name="postal_code",
            hint="US ZIP code format",
            required=False,
        )
        assert field.name == "postal_code"
        assert field.hint == "US ZIP code format"
        assert field.required is False


class TestFormInput:
    """Tests for FormInput model."""

    def test_basic_form(self):
        """Test creating a basic form input."""
        form = FormInput(fields=["username", "password"])
        assert len(form.fields) == 2
        assert form.context is None

    def test_form_with_context(self):
        """Test form with context."""
        form = FormInput(
            fields=["email", "phone"],
            context="Contact information form",
            form_title="Contact Us",
        )
        assert form.context == "Contact information form"
        assert form.form_title == "Contact Us"


class TestFieldAnalysisInput:
    """Tests for FieldAnalysisInput model."""

    def test_analysis_input(self):
        """Test creating analysis input with hints."""
        fields = [
            FieldInput(name="code", hint="Programming language code"),
            FieldInput(name="level", hint="Skill level 1-10"),
        ]
        analysis = FieldAnalysisInput(
            fields=fields,
            context="Developer skills assessment",
        )
        assert len(analysis.fields) == 2
        assert analysis.context == "Developer skills assessment"


class TestFormFieldSchema:
    """Tests for FormFieldSchema model."""

    def test_basic_field(self):
        """Test creating a basic field schema."""
        field = FormFieldSchema(
            name="email",
            type="string",
            title="Email Address",
            format="email",
        )
        assert field.name == "email"
        assert field.type == "string"
        assert field.format == "email"

    def test_field_with_validation(self):
        """Test field with validation rules."""
        field = FormFieldSchema(
            name="password",
            type="string",
            title="Password",
            min_length=8,
            max_length=128,
        )
        assert field.min_length == 8
        assert field.max_length == 128


class TestGeneratedFormSchema:
    """Tests for GeneratedFormSchema model."""

    def test_schema_creation(self):
        """Test creating a form schema."""
        schema = GeneratedFormSchema(
            form_id="test",
            title="Test Form",
            fields=[
                FormFieldSchema(
                    name="email",
                    type="string",
                    title="Email",
                    format="email",
                    required=True,
                ),
                FormFieldSchema(
                    name="age",
                    type="integer",
                    title="Age",
                    required=False,
                ),
            ],
        )
        assert schema.form_id == "test"
        assert len(schema.fields) == 2

    def test_schema_export(self):
        """Test exporting complete form schema."""
        schema = GeneratedFormSchema(
            form_id="test",
            title="Test Form",
            fields=[
                FormFieldSchema(
                    name="username",
                    type="string",
                    title="Username",
                    required=True,
                ),
            ],
        )
        json_schema = schema.to_json_schema()
        assert json_schema["type"] == "object"
        assert "username" in json_schema["properties"]
        assert "username" in json_schema["required"]

    def test_form_config_export(self):
        """Test exporting form configuration."""
        schema = GeneratedFormSchema(
            form_id="login",
            title="Login",
            fields=[
                FormFieldSchema(
                    name="password",
                    type="string",
                    title="Password",
                    ui_widget="password",
                ),
            ],
        )
        config = schema.to_form_config()
        assert config["formId"] == "login"
        assert "schema" in config
        assert "uiSchema" in config

    def test_ui_schema_export(self):
        """Test exporting UI schema."""
        schema = GeneratedFormSchema(
            form_id="test",
            title="Test",
            fields=[
                FormFieldSchema(
                    name="email",
                    type="string",
                    title="Email",
                    ui_widget="email",
                    placeholder="Enter your email",
                ),
            ],
        )
        ui_schema = schema.to_ui_schema()
        assert "email" in ui_schema
        assert ui_schema["email"]["ui:widget"] == "email"
        assert ui_schema["email"]["ui:placeholder"] == "Enter your email"


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(
            is_valid=True,
            validated_data={"email": "test@example.com"},
        )
        assert result.is_valid
        assert result.error_count == 0

    def test_invalid_result(self):
        """Test invalid validation result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=[
                FieldValidationError(
                    field_name="email",
                    error_type="format",
                    message="Invalid email format",
                ),
            ],
        )
        assert not result.is_valid
        assert result.error_count == 1
        assert len(result.get_field_errors("email")) == 1

    def test_error_dict_conversion(self):
        """Test converting errors to dict format."""
        result = ValidationResult(
            is_valid=False,
            errors=[
                FieldValidationError(
                    field_name="email",
                    error_type="format",
                    message="Invalid email format",
                ),
                FieldValidationError(
                    field_name="email",
                    error_type="required",
                    message="Email is required",
                ),
                FieldValidationError(
                    field_name="age",
                    error_type="minimum",
                    message="Must be at least 18",
                ),
            ],
        )
        error_dict = result.to_error_dict()
        assert len(error_dict["email"]) == 2
        assert len(error_dict["age"]) == 1
