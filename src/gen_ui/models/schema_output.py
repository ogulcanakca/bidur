"""
JSON Schema output models for form generation.

These models represent the structured output that the agent produces,
which can be used by client-side form libraries like react-jsonschema-form.
"""

from typing import Any

from pydantic import BaseModel, Field


class FormFieldSchema(BaseModel):
    """Schema for a single form field."""
    
    name: str = Field(..., description="Field name/key")
    type: str = Field(..., description="JSON Schema type: string, number, integer, boolean")
    title: str = Field(..., description="Human-readable label")
    description: str | None = Field(default=None, description="Help text")
    format: str | None = Field(default=None, description="Format: email, uri, date, password, etc.")
    
    # Validation
    required: bool = Field(default=True, description="Whether field is required")
    min_length: int | None = Field(default=None, description="Minimum string length")
    max_length: int | None = Field(default=None, description="Maximum string length")
    minimum: float | None = Field(default=None, description="Minimum numeric value")
    maximum: float | None = Field(default=None, description="Maximum numeric value")
    pattern: str | None = Field(default=None, description="Regex pattern")
    enum_values: list[str] | None = Field(default=None, description="Allowed values for select")
    
    # UI
    ui_widget: str = Field(default="text", description="UI widget type")
    placeholder: str | None = Field(default=None, description="Placeholder text")


class GeneratedFormSchema(BaseModel):
    """
    Complete generated form schema output.
    
    This is a flat structure that's compatible with OpenAI's strict JSON schema.
    """
    
    form_id: str = Field(..., description="Form identifier")
    title: str = Field(..., description="Form title")
    description: str | None = Field(default=None, description="Form description")
    fields: list[FormFieldSchema] = Field(..., description="List of form fields")
    submit_button_text: str = Field(default="Submit", description="Submit button text")

    def to_json_schema(self) -> dict[str, Any]:
        """Export as JSON Schema dict."""
        properties = {}
        required = []
        
        for field in self.fields:
            prop: dict[str, Any] = {
                "type": field.type,
                "title": field.title,
            }
            if field.description:
                prop["description"] = field.description
            if field.format:
                prop["format"] = field.format
            if field.min_length is not None:
                prop["minLength"] = field.min_length
            if field.max_length is not None:
                prop["maxLength"] = field.max_length
            if field.minimum is not None:
                prop["minimum"] = field.minimum
            if field.maximum is not None:
                prop["maximum"] = field.maximum
            if field.pattern:
                prop["pattern"] = field.pattern
            if field.enum_values:
                prop["enum"] = field.enum_values
            
            properties[field.name] = prop
            
            if field.required:
                required.append(field.name)
        
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "title": self.title,
            "description": self.description,
            "properties": properties,
            "required": required,
        }

    def to_ui_schema(self) -> dict[str, Any]:
        """Export as UI Schema dict."""
        ui_schema: dict[str, Any] = {}
        
        for field in self.fields:
            field_ui: dict[str, Any] = {}
            if field.ui_widget:
                field_ui["ui:widget"] = field.ui_widget
            if field.placeholder:
                field_ui["ui:placeholder"] = field.placeholder
            if field_ui:
                ui_schema[field.name] = field_ui
        
        return ui_schema

    def to_form_config(self) -> dict[str, Any]:
        """Export complete form configuration for client libraries."""
        return {
            "formId": self.form_id,
            "schema": self.to_json_schema(),
            "uiSchema": self.to_ui_schema(),
            "submitButtonText": self.submit_button_text,
        }


class JSONSchemaProperty(BaseModel):
    """JSON Schema property (for manual construction)."""
    
    type: str = Field(..., description="JSON Schema type")
    title: str | None = Field(default=None)
    description: str | None = Field(default=None)
    format: str | None = Field(default=None)
    min_length: int | None = Field(default=None, alias="minLength")
    max_length: int | None = Field(default=None, alias="maxLength")
    minimum: float | None = Field(default=None)
    maximum: float | None = Field(default=None)
    pattern: str | None = Field(default=None)
    enum: list[str] | None = Field(default=None)
    
    model_config = {"populate_by_name": True}
    
    def model_dump_json_schema(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class UISchemaProperty(BaseModel):
    """UI Schema property (for manual construction)."""
    
    ui_widget: str | None = Field(default=None, alias="ui:widget")
    ui_placeholder: str | None = Field(default=None, alias="ui:placeholder")
    
    model_config = {"populate_by_name": True}
    
    def model_dump_ui_schema(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)
