/**
 * Gen-UI Form JavaScript
 * 
 * Handles form generation, rendering, and submission.
 */

// Get URL parameters (from query string or path)
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const path = window.location.pathname;

    // Check if this is a short URL: /form/{session_id}
    const shortUrlMatch = path.match(/^\/form\/([a-zA-Z0-9]+)$/);

    return {
        fields: params.get("fields") || "",
        context: params.get("context") || null,
        sessionId: params.get("session_id") || (shortUrlMatch ? shortUrlMatch[1] : null),
        isShortUrl: !!shortUrlMatch,
    };
}

// Show/hide sections
function showSection(id) {
    document.querySelectorAll("[id$='-container'], #loading, #error").forEach(el => {
        el.style.display = "none";
    });
    const element = document.getElementById(id);
    if (element) element.style.display = "block";
}

function showError(message) {
    document.getElementById("error-message").textContent = message;
    showSection("error");
}

// Generate form from schema
async function generateForm() {
    const params = getUrlParams();
    let preGeneratedSchema = null;

    // If short URL, fetch config from API first
    if (params.isShortUrl && params.sessionId) {
        showSection("loading");

        try {
            const configResponse = await fetch(`/api/form-config/${params.sessionId}`);
            const configData = await configResponse.json();

            if (!configResponse.ok || !configData.success) {
                throw new Error(configData.error || "Form config not found");
            }

            // Update params with config from API
            params.fields = configData.fields.join(",");
            params.context = configData.context;

            // Check if schema is pre-generated
            if (configData.schema) {
                preGeneratedSchema = configData.schema;
            }
        } catch (error) {
            showError(`Error: ${error.message}`);
            return;
        }
    }

    if (!params.fields) {
        showError("No fields specified. Add ?fields=field1,field2 to the URL.");
        return;
    }

    showSection("loading");

    try {
        let data;

        // Use pre-generated schema if available
        if (preGeneratedSchema) {
            data = preGeneratedSchema;
        } else {
            // Fallback to API call
            const url = `/api/schema?fields=${encodeURIComponent(params.fields)}` +
                (params.context ? `&context=${encodeURIComponent(params.context)}` : "");

            const response = await fetch(url);
            data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Failed to generate form");
            }
        }

        renderForm(data);
    } catch (error) {
        showError(`Error generating form: ${error.message}`);
    }
}

// Render form from schema
function renderForm(schemaData) {
    const { title, description, schema, uiSchema, submitButtonText } = schemaData;

    document.getElementById("form-title").textContent = title;
    document.getElementById("form-description").textContent = description || "";
    document.getElementById("submit-btn").textContent = submitButtonText || "Submit";

    const formFields = document.getElementById("form-fields");
    formFields.innerHTML = "";

    const properties = schema.properties || {};
    const required = schema.required || [];

    for (const [fieldName, fieldSchema] of Object.entries(properties)) {
        const fieldDiv = document.createElement("div");
        fieldDiv.className = "form-field";

        const label = document.createElement("label");
        label.textContent = fieldSchema.title || fieldName;
        if (required.includes(fieldName)) {
            label.innerHTML += " <span class='required'>*</span>";
        }
        label.setAttribute("for", fieldName);

        const help = fieldSchema.description ?
            `<small class="help-text">${fieldSchema.description}</small>` : "";

        let input;
        const uiField = uiSchema[fieldName] || {};
        const widget = uiField["ui:widget"] || fieldSchema.format || fieldSchema.type;

        if (fieldSchema.enum) {
            // Select dropdown
            input = document.createElement("select");
            input.id = fieldName;
            input.name = fieldName;
            input.required = required.includes(fieldName);

            const placeholder = document.createElement("option");
            placeholder.value = "";
            placeholder.textContent = `Select ${fieldSchema.title || fieldName}`;
            input.appendChild(placeholder);

            fieldSchema.enum.forEach(value => {
                const option = document.createElement("option");
                option.value = value;
                option.textContent = value;
                input.appendChild(option);
            });
        } else if (fieldSchema.type === "boolean") {
            // Checkbox
            input = document.createElement("input");
            input.type = "checkbox";
            input.id = fieldName;
            input.name = fieldName;
        } else if (fieldSchema.type === "integer" || fieldSchema.type === "number") {
            // Number input (using text type to avoid browser native validation)
            // Note: Validation is handled server-side by validator agent
            input = document.createElement("input");
            input.type = "text";
            input.id = fieldName;
            input.name = fieldName;
            input.required = required.includes(fieldName);
            // Add pattern hint in placeholder if needed (for UX, not validation)
            if (!uiField["ui:placeholder"] && fieldSchema.type === "integer") {
                input.placeholder = "Enter a number";
            }
        } else if (widget === "password") {
            // Password input
            input = document.createElement("input");
            input.type = "password";
            input.id = fieldName;
            input.name = fieldName;
            input.required = required.includes(fieldName);
            // Note: minLength/maxLength removed - validation is handled server-side
        } else if (widget === "textarea") {
            // Textarea
            input = document.createElement("textarea");
            input.id = fieldName;
            input.name = fieldName;
            input.required = required.includes(fieldName);
            input.rows = 4;
            // Note: minLength/maxLength removed - validation is handled server-side
        } else {
            // Text input (default)
            // Note: Using "text" type for all inputs (including email) to avoid browser native validation
            // Validation is handled server-side by validator agent
            input = document.createElement("input");
            input.type = "text";
            input.id = fieldName;
            input.name = fieldName;
            input.required = required.includes(fieldName);
            if (uiField["ui:placeholder"]) input.placeholder = uiField["ui:placeholder"];
        }

        fieldDiv.appendChild(label);
        if (help) fieldDiv.innerHTML += help;
        fieldDiv.appendChild(input);
        formFields.appendChild(fieldDiv);
    }

    showSection("form-container");
}

// Handle form submission
document.getElementById("user-form").addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const data = {};

    for (const [key, value] of formData.entries()) {
        const field = e.target.querySelector(`[name="${key}"]`);
        if (field.type === "checkbox") {
            data[key] = field.checked;
        } else if (field.type === "number") {
            data[key] = field.value ? parseFloat(field.value) : null;
        } else {
            data[key] = value;
        }
    }

    // Add session_id to submission data
    const params = getUrlParams();
    if (params.sessionId) {
        data._session_id = params.sessionId;
    }

    try {
        const response = await fetch("/api/submit", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Failed to submit form");
        }

        // Show success
        document.getElementById("success-title").textContent =
            document.getElementById("form-title").textContent;
        document.getElementById("output-json").textContent =
            JSON.stringify(data, null, 2);
        showSection("success-container");
    } catch (error) {
        showError(`Error submitting form: ${error.message}`);
    }
});

// Fill again button
document.getElementById("fill-again-btn").addEventListener("click", () => {
    showSection("form-container");
});

// Initialize on page load
window.addEventListener("DOMContentLoaded", () => {
    generateForm();
});

