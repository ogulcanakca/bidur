"""
Tracing configuration for Gen-UI system.

This module provides tracing setup using OpenAI Agents SDK's built-in
tracing capabilities. Traces can be viewed in the OpenAI dashboard.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from agents import trace, set_tracing_disabled
from agents.tracing import (
    TracingProcessor,
    Trace,
    Span,
    add_trace_processor,
    set_trace_processors,
)


class ConsoleTracingProcessor(TracingProcessor):
    """
    A simple tracing processor that logs traces to the console.
    
    Useful for development and debugging.
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the console tracing processor.
        
        Args:
            verbose: If True, print detailed span information.
        """
        self.verbose = verbose
    
    def on_trace_start(self, trace: Trace) -> None:
        """Called when a trace starts."""
        print(f"\n[TRACE START] {trace.name} (ID: {trace.trace_id[:8]}...)")
    
    def on_trace_end(self, trace: Trace) -> None:
        """Called when a trace ends."""
        print(f"[TRACE END] {trace.name}")
    
    def on_span_start(self, span: Span[object]) -> None:
        """Called when a span starts."""
        if self.verbose:
            print(f"  ├─ [SPAN START] {span.span_data}")
    
    def on_span_end(self, span: Span[object]) -> None:
        """Called when a span ends."""
        if self.verbose:
            print(f"  └─ [SPAN END] {span.span_data}")
    
    def shutdown(self) -> None:
        """Called when the processor is shut down."""
        pass
    
    def force_flush(self) -> None:
        """Force flush any pending traces."""
        pass


class FileTracingProcessor(TracingProcessor):
    """
    A tracing processor that writes traces to a JSON file.
    
    Useful for persistent logging and later analysis.
    """
    
    def __init__(self, file_path: str = "traces.jsonl"):
        """
        Initialize the file tracing processor.
        
        Args:
            file_path: Path to the output file (JSON Lines format).
        """
        import json
        self.file_path = file_path
        self._json = json
        self._traces: list[dict] = []
    
    def on_trace_start(self, trace: Trace) -> None:
        """Called when a trace starts."""
        self._current_trace = {
            "trace_id": trace.trace_id,
            "name": trace.name,
            "spans": [],
        }
    
    def on_trace_end(self, trace: Trace) -> None:
        """Called when a trace ends."""
        if hasattr(self, "_current_trace"):
            with open(self.file_path, "a") as f:
                f.write(self._json.dumps(self._current_trace) + "\n")
    
    def on_span_start(self, span: Span[object]) -> None:
        """Called when a span starts."""
        pass
    
    def on_span_end(self, span: Span[object]) -> None:
        """Called when a span ends."""
        if hasattr(self, "_current_trace"):
            self._current_trace["spans"].append({
                "span_id": span.span_id,
                "data": str(span.span_data),
            })
    
    def shutdown(self) -> None:
        """Called when the processor is shut down."""
        pass
    
    def force_flush(self) -> None:
        """Force flush any pending traces."""
        pass


def setup_tracing(
    enabled: bool = True,
    console: bool = True,
    verbose: bool = False,
    file_path: str | None = None,
) -> None:
    """
    Configure tracing for the Gen-UI system.
    
    By default, traces are sent to the OpenAI dashboard if you have
    an OpenAI API key configured.
    
    Args:
        enabled: Whether tracing is enabled.
        console: Whether to print traces to console.
        verbose: Whether to print detailed span information.
        file_path: Optional file path to write traces to.
        
    Example:
        >>> from gen_ui.tracing import setup_tracing
        >>> setup_tracing(console=True, verbose=True)
        >>> # Now all agent runs will be traced
    """
    if not enabled:
        set_tracing_disabled(True)
        return
    
    set_tracing_disabled(False)
    
    processors: list[TracingProcessor] = []
    
    if console:
        processors.append(ConsoleTracingProcessor(verbose=verbose))
    
    if file_path:
        processors.append(FileTracingProcessor(file_path=file_path))
    
    if processors:
        set_trace_processors(processors)


def disable_tracing() -> None:
    """Disable all tracing."""
    set_tracing_disabled(True)


def enable_tracing() -> None:
    """Enable tracing (uses default OpenAI dashboard)."""
    set_tracing_disabled(False)


@asynccontextmanager
async def traced_operation(
    name: str,
    metadata: dict | None = None,
) -> AsyncGenerator[None, None]:
    """
    Context manager for tracing a specific operation.
    
    Args:
        name: Name of the operation to trace.
        metadata: Optional metadata to attach to the trace.
        
    Example:
        >>> async with traced_operation("form_generation"):
        ...     schema = await orchestrator.generate_form(fields)
    """
    with trace(name):
        yield


def trace_form_generation(func):
    """Decorator to trace form generation operations."""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        with trace("form_generation"):
            return await func(*args, **kwargs)
    
    return wrapper


def trace_validation(func):
    """Decorator to trace validation operations."""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        with trace("validation"):
            return await func(*args, **kwargs)
    
    return wrapper

