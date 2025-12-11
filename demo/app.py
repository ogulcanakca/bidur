"""
bidur Demo - Interactive Form Generation Demo

This Gradio app demonstrates the bidur MCP server by:
1. Connecting to the remote MCP server on Render
2. Calling the collect_user_input tool
3. Displaying the form URL and results
"""

import asyncio
import gradio as gr
import httpx

# Default MCP Server URL (Render deployment)
DEFAULT_FORM_URL = "https://gen-ui-form-server.onrender.com"


async def generate_form(fields: str, context: str, api_key: str):
    """Generate a form by calling the Form Server API."""
    if not fields.strip():
        return "❌ Please enter at least one field name", "", {}
    
    if not api_key.strip():
        return "❌ OpenAI API key is required", "", {}
    
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{DEFAULT_FORM_URL}/api/forms",
                json={
                    "fields": field_list,
                    "context": context if context.strip() else None,
                },
                headers={
                    "Content-Type": "application/json",
                    "X-OpenAI-API-Key": api_key,
                },
            )
            
            if response.status_code == 200:
                result = response.json()
                form_url = f"{DEFAULT_FORM_URL}{result.get('form_url', '')}"
                session_id = result.get("session_id", "")
                
                # Create clickable link markdown
                link_md = f"""
## ✅ Form Created!

### 👉 [Click here to open the form]({form_url})

**Session ID:** `{session_id}`

**Fields:** {', '.join(field_list)}

---
*Copy the session ID to check submission status in the next tab.*
"""
                return link_md, session_id, {"form_url": form_url, "fields": field_list}
            else:
                return f"❌ Server error: {response.status_code}", "", {}
                
    except httpx.ConnectError:
        return "❌ Could not connect to Form Server. It may be starting up (cold start ~30-60s). Please try again.", "", {}
    except Exception as e:
        return f"❌ Error: {str(e)}", "", {}


async def check_submission(session_id: str):
    """Check if a form has been submitted."""
    if not session_id.strip():
        return "❌ Please enter a session ID", {}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{DEFAULT_FORM_URL}/api/submission/{session_id}"
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("submitted"):
                    data = result.get("data", {})
                    md = f"""
## ✅ Form Submitted!

The user has filled out the form. Here's the collected data:
"""
                    return md, data
                else:
                    return "⏳ Waiting for user to submit the form...", {}
            else:
                return "⏳ No submission yet. User hasn't filled the form.", {}
                
    except Exception as e:
        return f"❌ Error: {str(e)}", {}


def sync_generate_form(fields, context, api_key):
    return asyncio.run(generate_form(fields, context, api_key))


def sync_check_submission(session_id):
    return asyncio.run(check_submission(session_id))


# Create Gradio Interface
with gr.Blocks(title="bidur Demo") as demo:
    gr.Markdown("""
# 📝 bidur Demo

> *Bi dur, some info is missing! Let me generate UI to gather the missing pieces.*

**How it works:**
1. Enter your OpenAI API key
2. Enter field names (comma-separated)
3. Click "Generate Form" → Get a link
4. Open the link in new tab → Fill the form
5. Check submission status
    """)
    
    with gr.Tab("🎯 Generate Form"):
        with gr.Row():
            with gr.Column(scale=1):
                api_key_input = gr.Textbox(
                    label="🔑 OpenAI API Key",
                    placeholder="sk-...",
                    type="password",
                )
                fields_input = gr.Textbox(
                    label="📋 Field Names",
                    placeholder="username, email, password, birth_date",
                    info="Comma-separated",
                )
                context_input = gr.Textbox(
                    label="📝 Context (optional)",
                    placeholder="User registration form",
                )
                generate_btn = gr.Button("🚀 Generate Form", variant="primary", size="lg")
            
            with gr.Column(scale=1):
                result_md = gr.Markdown(label="Result")
                session_output = gr.Textbox(label="Session ID (copy this)", interactive=True)
                result_json = gr.JSON(label="Details", visible=True)
        
        generate_btn.click(
            fn=sync_generate_form,
            inputs=[fields_input, context_input, api_key_input],
            outputs=[result_md, session_output, result_json],
        )
    
    with gr.Tab("📬 Check Submission"):
        with gr.Row():
            with gr.Column(scale=1):
                session_input = gr.Textbox(
                    label="🔍 Session ID",
                    placeholder="Paste session ID from previous step",
                )
                check_btn = gr.Button("� Check Status", variant="secondary", size="lg")
            
            with gr.Column(scale=1):
                status_md = gr.Markdown(label="Status")
                submission_data = gr.JSON(label="Submitted Data")
        
        check_btn.click(
            fn=sync_check_submission,
            inputs=session_input,
            outputs=[status_md, submission_data],
        )
    
    gr.Markdown("""
---
**Links:** 
- [GitHub Repository](https://github.com/ogulcanakca/bidur) 
- [Demo Source Code](https://github.com/ogulcanakca/bidur/tree/main/demo)
- [MCP Server Health](https://gen-ui-mcp-server.onrender.com/health) 
- [Form Server Health](https://gen-ui-form-server.onrender.com/health)

*Note: Render free tier has cold starts (~30-60s). Please be patient on first request.*
    """)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
