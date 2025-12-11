"""
Simple HTTP server for HTML/JS UI.

This server provides:
1. Static file serving (HTML, JS, CSS)
2. API endpoint for schema generation
3. API endpoint for form submission

Usage:
    python ui/html/server.py
    # Then open http://localhost:8080
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from gen_ui import generate_form
from gen_ui.config import get_config


# In-memory form config cache
form_cache = {}

# In-memory submission cache (for remote polling)
submission_cache = {}


class FormHandler(BaseHTTPRequestHandler):
    """HTTP handler for form UI and API endpoints."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/api/schema":
            self.handle_schema_request(parsed_path)
            return
        
        # Form config API for short URLs
        if path.startswith("/api/form-config/"):
            self.handle_form_config_request(path)
            return
        
        if path == "/health":
            self.handle_health_check()
            return
        
        # Short URL: /form/{session_id}
        if path.startswith("/form/"):
            self.handle_short_form_url(path)
            return
        
        if path == "/" or path == "/index.html":
            self.serve_file("index.html", "text/html")
        elif path == "/form.js":
            self.serve_file("form.js", "application/javascript")
        elif path == "/form.css":
            self.serve_file("form.css", "text/css")
        # Submission polling API
        elif path.startswith("/api/submission/"):
            self.handle_get_submission(path)
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == "/api/submit":
            self.handle_submit_request()
        elif path == "/api/forms":
            self.handle_create_form()
        else:
            self.send_error(404, "Not Found")
    
    def handle_create_form(self):
        """Handle form creation via POST /api/forms."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        # Get optional OpenAI API key from header
        openai_api_key = self.headers.get("X-OpenAI-API-Key")
        
        try:
            data = json.loads(post_data.decode("utf-8"))
            session_id = data.get("session_id")
            fields = data.get("fields", [])
            context = data.get("context")
            
            if not session_id:
                session_id = str(uuid.uuid4()).replace("-", "")
            
            if not fields:
                self.send_json_response({"error": "fields is required"}, 400)
                return
            
            # Generate schema now if API key is provided
            schema_data = None
            if openai_api_key:
                try:
                    # Temporarily set API key for this request
                    import os
                    old_key = os.environ.get("OPENAI_API_KEY")
                    os.environ["OPENAI_API_KEY"] = openai_api_key
                    
                    schema = asyncio.run(generate_form(fields=fields, context=context))
                    schema_data = {
                        "formId": schema.form_id,
                        "title": schema.title,
                        "description": schema.description,
                        "schema": schema.to_json_schema(),
                        "uiSchema": schema.to_ui_schema(),
                        "submitButtonText": schema.submit_button_text,
                    }
                    
                    # Restore old key
                    if old_key:
                        os.environ["OPENAI_API_KEY"] = old_key
                    else:
                        del os.environ["OPENAI_API_KEY"]
                except Exception as e:
                    print(f"Schema generation failed: {e}")
            
            # Store in cache (including pre-generated schema)
            form_cache[session_id] = {
                "fields": fields,
                "context": context,
                "openai_api_key": openai_api_key,
                "schema": schema_data,  # Pre-generated schema
            }
            
            form_url = f"/form/{session_id}"
            
            self.send_json_response({
                "success": True,
                "session_id": session_id,
                "form_url": form_url,
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
    
    def handle_short_form_url(self, path):
        """Handle short form URL: /form/{session_id}."""
        session_id = path.replace("/form/", "").strip("/")
        
        if not session_id:
            self.send_error(400, "Session ID required")
            return
        
        # Serve index.html directly - JS will fetch config from API
        self.serve_file("index.html", "text/html")
    
    def handle_form_config_request(self, path):
        """Handle form config API request: /api/form-config/{session_id}."""
        session_id = path.replace("/api/form-config/", "").strip("/")
        
        if not session_id:
            self.send_json_response({"error": "Session ID required"}, 400)
            return
        
        config = form_cache.get(session_id)
        
        if config:
            response = {
                "success": True,
                "session_id": session_id,
                "fields": config["fields"],
                "context": config.get("context"),
                "has_api_key": bool(config.get("openai_api_key")),
            }
            # Include pre-generated schema if available
            if config.get("schema"):
                response["schema"] = config["schema"]
            
            self.send_json_response(response)
        else:
            self.send_json_response({
                "success": False,
                "error": "Form config not found",
            }, 404)
    
    def handle_health_check(self):
        """Handle health check endpoint for microservices."""
        config = get_config()
        self.send_json_response({
            "status": "healthy",
            "service": "gen-ui-form",
            "port": config.server_port,
        })
    
    def handle_get_submission(self, path):
        """Handle GET /api/submission/{session_id} for remote polling."""
        session_id = path.replace("/api/submission/", "").strip("/")
        
        if not session_id:
            self.send_json_response({"error": "Session ID required"}, 400)
            return
        
        submission = submission_cache.get(session_id)
        
        if submission:
            self.send_json_response({
                "success": True,
                "session_id": session_id,
                "submitted": True,
                "data": submission,
            })
        else:
            self.send_json_response({
                "success": True,
                "session_id": session_id,
                "submitted": False,
            }, 404)
    
    def handle_schema_request(self, parsed_path):
        """Handle schema generation API request."""
        query_params = parse_qs(parsed_path.query)
        fields_param = query_params.get("fields", [""])[0]
        context = query_params.get("context", [None])[0]
        
        if not fields_param:
            self.send_json_response({"error": "fields parameter required"}, 400)
            return
        
        fields = [f.strip() for f in fields_param.split(",") if f.strip()]
        
        try:
            schema = asyncio.run(generate_form(fields=fields, context=context))
            
            response = {
                "formId": schema.form_id,
                "title": schema.title,
                "description": schema.description,
                "schema": schema.to_json_schema(),
                "uiSchema": schema.to_ui_schema(),
                "submitButtonText": schema.submit_button_text,
            }
            
            self.send_json_response(response)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)
    
    def handle_submit_request(self):
        """Handle form submission."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        try:
            form_data = json.loads(post_data.decode("utf-8"))
            
            session_id = form_data.get("_session_id") or self.headers.get("X-Session-ID")
            
            if not session_id:
                session_id = str(uuid.uuid4())
            
            project_root = None
            server_file = Path(__file__).resolve()
            
            if "GEN_UI_PROJECT_ROOT" in os.environ:
                project_root = Path(os.environ["GEN_UI_PROJECT_ROOT"]).resolve()
                if not (project_root / "pyproject.toml").exists():
                    project_root = None
            
            if project_root is None:
                for parent in server_file.parents:
                    if (parent / "pyproject.toml").exists():
                        project_root = parent
                        break
                
                if project_root is None:
                    for parent in server_file.parents:
                        if (parent / "src" / "gen_ui").exists():
                            project_root = parent
                            break
                
                if project_root is None:
                    project_root = server_file.parent.parent.parent

            
            cache_dir = project_root / ".cache" / "submissions"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = cache_dir / f"{session_id}_submission.json"
            
            debug_info = {
                "project_root": str(project_root),
                "cache_dir": str(cache_dir),
                "output_path": str(output_path),
                "session_id": session_id,
            }
            
            try:
                json_content = json.dumps(form_data, indent=2)
                
                temp_path = output_path.with_suffix('.tmp')
                
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(json_content)
                    f.flush()
                    os.fsync(f.fileno())
                
                if output_path.exists():
                    try:
                        output_path.unlink()
                    except OSError:
                        pass
                
                try:
                    temp_path.replace(output_path)
                except OSError as rename_error:
                    import shutil
                    try:
                        shutil.move(str(temp_path), str(output_path))
                    except Exception as move_error:
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                        raise OSError(
                            f"Failed to atomically write file: "
                            f"replace() failed: {rename_error}, "
                            f"move() failed: {move_error}"
                        )
                
                if not output_path.exists():
                    raise FileNotFoundError("File was not created after rename")
                
                file_saved = True
                error_msg = None
                
                # Also save to in-memory cache for remote polling
                submission_cache[session_id] = form_data
            except Exception as save_error:
                file_saved = False
                error_msg = str(save_error)
                # Still save to cache even if file save fails
                submission_cache[session_id] = form_data
            
            self.send_json_response({
                "success": file_saved,
                "message": "Form submitted successfully" if file_saved else f"Form submitted but file save failed: {error_msg}",
                "session_id": session_id,
                "data": form_data,
                "debug": debug_info if not file_saved else None,
            })
        except Exception as e:
            error_traceback = str(e)
            import traceback
            try:
                error_traceback = traceback.format_exc()
            except:
                pass
            print(f"[ERROR] Exception in handle_submit_request: {error_traceback}", file=sys.stderr, flush=True)
            self.send_json_response({"error": str(e), "traceback": error_traceback}, 500)
    
    def serve_file(self, filename, content_type):
        """Serve a static file."""
        server_dir = Path(__file__).parent.absolute()
        file_path = server_dir / filename
        
        if not file_path.exists():
            self.send_error(404, f"File not found: {file_path}")
            return
        
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))
    
    def send_json_response(self, data, status=200):
        """Send JSON response."""
        json_data = json.dumps(data, indent=2).encode("utf-8")
        
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(json_data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json_data)
    
    def log_message(self, format, *args):
        """Override to reduce logging noise, but keep important messages."""
        message = format % args
        if "[DEBUG]" in message or "submission" in message.lower():
            print(message, file=sys.stderr, flush=True)


def main():
    """Start the HTTP server."""
    config = get_config()
    port = config.server_port
    server_address = ("", port)
    httpd = HTTPServer(server_address, FormHandler)
    
    print(f"Gen-UI HTML/JS Server running on http://localhost:{port}")
    print(f"   Open http://localhost:{port} in your browser")
    print("   Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        httpd.shutdown()


if __name__ == "__main__":
    main()

